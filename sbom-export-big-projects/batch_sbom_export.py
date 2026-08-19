#!/usr/bin/env python3
"""
Batch SBOM Exporter for Endor Labs REST API.

Mirrors the batching strategy used by endorctl's sbom export command:
split package-version UUIDs into batches of N, call the sbom-export API
for each batch, then merge the resulting SBOMs client-side.

This avoids timeouts on large projects with many packages/dependencies.
"""

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.endorlabs.com"
# Larger batches mean fewer round trips, which is viable because
# Request-Timeout gives the server far more than its 20s default per call.
DEFAULT_BATCH_SIZE = 25
DEFAULT_TIMEOUT = 120
# The API allows each request 20s by default, and a slow one returns 504.
# The client must outwait the server or it aborts before that 504 arrives.
CLIENT_TIMEOUT_BUFFER = 30
DEFAULT_PAGE_SIZE = 500
RETRY_DELAY_SECONDS = 2
MAX_RETRIES = 5
DEFAULT_WORKERS = 8

SBOM_KIND = {
    "cyclonedx": 1,
    "spdx": 2,
}
OUTPUT_FORMAT = {
    "json": 1,
    "xml": 2,
    "tag-value": 3,
}
COMPONENT_TYPE = {
    "library": 1,
    "application": 2,
}


def get_headers(token: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    Build HTTP headers for Endor Labs API calls.

    Request-Timeout tells the API how many seconds it may spend on the
    request before returning a gateway timeout.
    """
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Request-Timeout": str(timeout),
    }


class IncompleteListing(Exception):
    """Fewer package versions were listed than the project reports."""


def _list_params(project_uuid: str, after_uuid: str | None = None) -> dict:
    """
    Base list parameters for the package-version query.

    Deliberately no sort. The endpoint already returns rows in ascending
    uuid order, and asking for that order explicitly is measurably
    catastrophic: a page costs ~0.4s unsorted and ~139s with
    list_parameters.sort.path=uuid.
    """
    conditions = [
        f'spec.project_uuid=="{project_uuid}"',
        'context.type=="CONTEXT_TYPE_MAIN"',
    ]
    if after_uuid:
        conditions.append(f'uuid>"{after_uuid}"')

    return {
        "list_parameters.filter": " and ".join(conditions),
        "list_parameters.mask": "uuid,meta.name",
    }


def count_package_versions(
    namespace: str,
    project_uuid: str,
    headers: dict,
    timeout: int = DEFAULT_TIMEOUT,
) -> int:
    """Return the total package-version count, used for progress logging."""
    params = _list_params(project_uuid)
    params["list_parameters.count"] = "true"

    resp = requests.get(
        f"{BASE_URL}/v1/namespaces/{namespace}/package-versions",
        headers=headers,
        params=params,
        timeout=timeout + CLIENT_TIMEOUT_BUFFER,
    )
    resp.raise_for_status()
    return resp.json().get("count_response", {}).get("count", 0)


def get_package_version_uuids_for_project(
    namespace: str,
    project_uuid: str,
    headers: dict,
    page_size: int = DEFAULT_PAGE_SIZE,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict]:
    """
    Walk every package version, using the highest uuid on each page as the
    cursor for the next request.

    Returns a list of dicts with 'uuid' and 'name' keys.
    """
    try:
        total = count_package_versions(
            namespace, project_uuid, headers, timeout
        )
    except requests.RequestException as exc:
        logger.warning("Could not fetch total count for progress: %s", exc)
        total = 0

    package_versions: list[dict] = []
    seen: set[str] = set()
    after_uuid = None

    while True:
        params = _list_params(project_uuid, after_uuid=after_uuid)
        params["list_parameters.page_size"] = page_size

        data = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(
                    f"{BASE_URL}/v1/namespaces/{namespace}/package-versions",
                    headers=headers,
                    params=params,
                    timeout=timeout + CLIENT_TIMEOUT_BUFFER,
                )
                resp.raise_for_status()
                data = resp.json()
                break
            except requests.RequestException as exc:
                if attempt == MAX_RETRIES - 1:
                    logger.error(
                        "Listing after uuid=%s failed after %d attempts, "
                        "collected %d so far: %s",
                        after_uuid or "start",
                        MAX_RETRIES,
                        len(package_versions),
                        exc,
                    )
                    raise
                delay = RETRY_DELAY_SECONDS * 2**attempt
                logger.warning(
                    "Listing after uuid=%s failed (attempt %d/%d), retrying "
                    "in %ds: %s",
                    after_uuid or "start",
                    attempt + 1,
                    MAX_RETRIES,
                    delay,
                    exc,
                )
                time.sleep(delay)

        objects = data.get("list", {}).get("objects", [])
        if not objects:
            break

        uuids = [pv.get("uuid", "") for pv in objects]

        # Advancing the cursor past the page maximum is only safe while the
        # natural order is ascending. If it ever isn't, rows below that
        # maximum get skipped, so say so loudly rather than lose packages.
        if any(b < a for a, b in zip(uuids, uuids[1:])):
            logger.warning(
                "Page after uuid=%s came back out of ascending order. Keyset "
                "paging assumes ascending uuids; this export may be missing "
                "package versions.",
                after_uuid or "start",
            )

        for pv in objects:
            uuid = pv.get("uuid", "")
            if uuid and uuid not in seen:
                seen.add(uuid)
                package_versions.append({
                    "uuid": uuid,
                    "name": pv.get("meta", {}).get("name", ""),
                })

        if total:
            logger.info(
                "Listed %d of %d package versions...",
                len(package_versions),
                total,
            )
        else:
            logger.info("Listed %d package versions...", len(package_versions))

        page_max = max(uuids)
        # A cursor that fails to advance would refetch the same page forever.
        if not page_max or (after_uuid and page_max <= after_uuid):
            logger.warning(
                "Cursor stopped advancing at uuid=%s; ending listing early.",
                after_uuid,
            )
            break
        after_uuid = page_max

    # A short page is not a reliable end-of-data signal: if the server caps
    # page_size below what was asked for, every page looks short. Trust the
    # count instead, and refuse to export a partial package list.
    if total and len(package_versions) < total:
        raise IncompleteListing(
            f"listed {len(package_versions)} of {total} package versions; "
            f"refusing to export an SBOM that is missing packages"
        )
    if total and len(package_versions) > total:
        logger.warning(
            "Listed %d package versions but the count reported %d; the "
            "project was likely rescanned mid-listing.",
            len(package_versions),
            total,
        )

    return package_versions


def export_sbom_batch(
    namespace: str,
    uuid_batch: list[str],
    app_name: str,
    headers: dict,
    sbom_kind: str = "cyclonedx",
    output_format: str = "json",
    component_type: str = "application",
    timeout: int = DEFAULT_TIMEOUT,
) -> list[str]:
    """
    Call the sbom-export API for a batch of package-version UUIDs.

    Retries with backoff, then halves the batch and exports each half, so a
    batch too expensive for the server degrades instead of failing the run.
    A single UUID that still fails raises, because dropping it would produce
    an SBOM silently missing packages.

    Returns the SBOM data strings produced for this batch.
    """
    url = f"{BASE_URL}/v1/namespaces/{namespace}/sbom-export"
    payload = {
        "tenant_meta": {"namespace": namespace},
        "meta": {"name": app_name},
        "spec": {
            "kind": SBOM_KIND[sbom_kind],
            "format": OUTPUT_FORMAT[output_format],
            "component_type": COMPONENT_TYPE[component_type],
            "export_parameters": {
                "package_version_uuids": uuid_batch,
            },
        },
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout + CLIENT_TIMEOUT_BUFFER,
            )
            if resp.status_code != 200:
                logger.debug(
                    "Response %d: %s", resp.status_code, resp.text[:500]
                )
            resp.raise_for_status()
            sbom_data = resp.json().get("spec", {}).get("data", "")
            if sbom_data:
                return [sbom_data]
            logger.warning(
                "Empty SBOM data for %d package version(s) starting %s",
                len(uuid_batch),
                uuid_batch[0],
            )
            return []
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES - 1:
                if len(uuid_batch) > 1:
                    half = len(uuid_batch) // 2
                    logger.warning(
                        "Batch of %d exhausted retries, splitting: %s",
                        len(uuid_batch),
                        exc,
                    )
                    return export_sbom_batch(
                        namespace,
                        uuid_batch[:half],
                        app_name,
                        headers,
                        sbom_kind,
                        output_format,
                        component_type,
                        timeout,
                    ) + export_sbom_batch(
                        namespace,
                        uuid_batch[half:],
                        app_name,
                        headers,
                        sbom_kind,
                        output_format,
                        component_type,
                        timeout,
                    )
                logger.error(
                    "Package version %s failed after %d attempts; aborting "
                    "rather than emitting an SBOM missing packages. Try a "
                    "longer --timeout: %s",
                    uuid_batch[0],
                    MAX_RETRIES,
                    exc,
                )
                raise
            delay = RETRY_DELAY_SECONDS * 2**attempt
            logger.warning(
                "Batch of %d failed (attempt %d/%d), retrying in %ds: %s",
                len(uuid_batch),
                attempt + 1,
                MAX_RETRIES,
                delay,
                exc,
            )
            time.sleep(delay)
    return []


def batch_export(
    namespace: str,
    uuids: list[str],
    app_name: str,
    headers: dict,
    batch_size: int = DEFAULT_BATCH_SIZE,
    workers: int = DEFAULT_WORKERS,
    **kwargs,
) -> list[str]:
    """
    Split UUIDs into batches and export them concurrently.

    Batches are independent and the merge deduplicates by PURL, so
    completion order does not matter.
    """
    batches = [
        uuids[i:i + batch_size] for i in range(0, len(uuids), batch_size)
    ]
    logger.info(
        "Exporting %d package versions in %d batches (%d at a time)...",
        len(uuids),
        len(batches),
        workers,
    )

    sbom_strings: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                export_sbom_batch,
                namespace,
                batch,
                app_name,
                headers,
                **kwargs,
            )
            for batch in batches
        ]
        try:
            for done, future in enumerate(as_completed(futures), start=1):
                sbom_strings.extend(future.result())
                logger.info("Exported batch %d/%d", done, len(batches))
        except BaseException:
            for future in futures:
                future.cancel()
            raise

    return sbom_strings


def merge_cyclonedx_sboms(sbom_strings: list[str], app_name: str) -> dict:
    """
    Merge multiple CycloneDX JSON SBOMs into one.

    Deduplicates components by PURL and merges dependency entries by ref,
    matching the logic in endorctl's sbomaggregator.go.
    """
    seen_components: dict[str, dict] = {}
    seen_dependencies: dict[str, dict] = {}
    merged_metadata = None

    for sbom_str in sbom_strings:
        sbom = json.loads(sbom_str)

        if merged_metadata is None:
            merged_metadata = deepcopy(sbom.get("metadata", {}))

        for comp in sbom.get("components", []):
            if comp.get("name") == app_name:
                continue
            key = comp.get("purl") or comp.get("bom-ref", comp.get("name", ""))
            seen_components[key] = comp

        for dep in sbom.get("dependencies", []):
            ref = dep.get("ref", "")
            if ref in seen_dependencies:
                existing = set(seen_dependencies[ref].get("dependsOn", []))
                existing.update(dep.get("dependsOn", []))
                seen_dependencies[ref]["dependsOn"] = sorted(existing)
            else:
                seen_dependencies[ref] = deepcopy(dep)

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "metadata": merged_metadata or {},
        "components": list(seen_components.values()),
        "dependencies": list(seen_dependencies.values()),
    }


def merge_spdx_sboms(sbom_strings: list[str], app_name: str) -> dict:
    """
    Merge multiple SPDX JSON SBOMs into one.

    Deduplicates packages by SPDXID and merges relationships.
    """
    seen_packages: dict[str, dict] = {}
    seen_relationships: dict[str, dict] = {}
    merged_base = None

    for sbom_str in sbom_strings:
        sbom = json.loads(sbom_str)

        if merged_base is None:
            merged_base = {
                "spdxVersion": sbom.get("spdxVersion", "SPDX-2.3"),
                "dataLicense": sbom.get("dataLicense", "CC0-1.0"),
                "SPDXID": sbom.get("SPDXID", "SPDXRef-DOCUMENT"),
                "name": sbom.get("name", app_name),
                "documentNamespace": sbom.get("documentNamespace", ""),
                "creationInfo": deepcopy(sbom.get("creationInfo", {})),
            }

        for pkg in sbom.get("packages", []):
            if pkg.get("name") == app_name:
                continue
            key = pkg.get("SPDXID", pkg.get("name", ""))
            seen_packages[key] = pkg

        for rel in sbom.get("relationships", []):
            key = (
                f"{rel.get('spdxElementId', '')}"
                f"-{rel.get('relationshipType', '')}"
                f"-{rel.get('relatedSpdxElement', '')}"
            )
            seen_relationships[key] = rel

    result = merged_base or {}
    result["packages"] = list(seen_packages.values())
    result["relationships"] = list(seen_relationships.values())
    return result


def run_export(
    namespace: str,
    token: str,
    project_uuid: str,
    app_name: str,
    sbom_kind: str = "cyclonedx",
    output_format: str = "json",
    component_type: str = "application",
    batch_size: int = DEFAULT_BATCH_SIZE,
    output_file: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    timeout: int = DEFAULT_TIMEOUT,
    workers: int = DEFAULT_WORKERS,
) -> dict:
    """Full batched SBOM export pipeline."""
    headers = get_headers(token, timeout=timeout)

    logger.info("Fetching package versions for project %s...", project_uuid)
    package_versions = get_package_version_uuids_for_project(
        namespace,
        project_uuid,
        headers,
        page_size=page_size,
        timeout=timeout,
    )
    if not package_versions:
        logger.error("No package versions found for project %s", project_uuid)
        sys.exit(1)

    uuids = [pv["uuid"] for pv in package_versions]
    logger.info("Found %d package versions.", len(uuids))

    sbom_strings = batch_export(
        namespace,
        uuids,
        app_name,
        headers,
        batch_size=batch_size,
        workers=workers,
        sbom_kind=sbom_kind,
        output_format=output_format,
        component_type=component_type,
        timeout=timeout,
    )

    if not sbom_strings:
        logger.error("No SBOM data returned for any batch.")
        sys.exit(1)

    logger.info("Merging %d batch responses...", len(sbom_strings))
    is_spdx = sbom_kind == "spdx"
    if is_spdx:
        merged = merge_spdx_sboms(sbom_strings, app_name)
    else:
        merged = merge_cyclonedx_sboms(sbom_strings, app_name)

    component_key = "packages" if is_spdx else "components"
    dep_key = "relationships" if is_spdx else "dependencies"
    logger.info(
        "Merged SBOM: %d %s, %d %s",
        len(merged.get(component_key, [])),
        component_key,
        len(merged.get(dep_key, [])),
        dep_key,
    )

    output = json.dumps(merged, indent=2)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output)
        logger.info("SBOM written to %s", output_file)
    else:
        print(output)

    return merged


def main():
    parser = argparse.ArgumentParser(
        description="Batch SBOM exporter for Endor Labs REST API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s \\
    --namespace my-namespace \\
    --token "$ENDOR_TOKEN" \\
    --project-uuid 6123abc... \\
    --app-name my-application

  %(prog)s \\
    --namespace my-namespace \\
    --token "$ENDOR_TOKEN" \\
    --project-uuid 6123abc... \\
    --app-name my-application \\
    --sbom-kind spdx \\
    --output sbom.json

  # large project: more export concurrency and a longer server budget
  %(prog)s \\
    --namespace my-namespace \\
    --token "$ENDOR_TOKEN" \\
    --project-uuid 6123abc... \\
    --app-name my-application \\
    --timeout 300 \\
    --workers 8 \\
    --output sbom.json
        """,
    )
    parser.add_argument("--namespace", required=True, help="Endor Labs namespace")
    parser.add_argument("--token", required=True, help="API bearer token")
    parser.add_argument(
        "--project-uuid", required=True, help="UUID of the project to export"
    )
    parser.add_argument(
        "--app-name",
        required=True,
        help="Application name for the SBOM (required for multi-package export)",
    )
    parser.add_argument(
        "--sbom-kind",
        default="cyclonedx",
        choices=["cyclonedx", "spdx"],
        help="SBOM standard (default: cyclonedx)",
    )
    parser.add_argument(
        "--output-format",
        default="json",
        choices=["json", "xml", "tag-value"],
        help="Output encoding (default: json)",
    )
    parser.add_argument(
        "--component-type",
        default="application",
        choices=["application", "library"],
        help="Component type (default: application)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=(
            f"UUIDs per sbom-export call (default: {DEFAULT_BATCH_SIZE}). "
            "Halved automatically if a batch keeps failing"
        ),
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help=(
            "Package versions per listing request "
            f"(default: {DEFAULT_PAGE_SIZE})"
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=(
            "Seconds the API may spend on each request, sent as the "
            f"Request-Timeout header (default: {DEFAULT_TIMEOUT}, API default "
            f"is 20). The client waits {CLIENT_TIMEOUT_BUFFER}s longer"
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=(
            "Concurrent sbom-export requests (default: "
            f"{DEFAULT_WORKERS}). Listing is always sequential"
        ),
    )
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    run_export(
        namespace=args.namespace,
        token=args.token,
        project_uuid=args.project_uuid,
        app_name=args.app_name,
        sbom_kind=args.sbom_kind,
        output_format=args.output_format,
        component_type=args.component_type,
        batch_size=args.batch_size,
        output_file=args.output,
        page_size=args.page_size,
        timeout=args.timeout,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
