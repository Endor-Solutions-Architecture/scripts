#!/usr/bin/env python3
"""
delete_long_lived_api_keys.py

Detect Endor Labs API keys whose total lifetime
(expiration_time - create_time) exceeds a threshold (default: 90 days),
and optionally delete them.

Safety model:
    * Default mode is DRY-RUN. The script prints what *would* be deleted.
    * Pass --delete to actually delete the offending keys.
    * Keys with no expiration_time are treated as "infinite lifetime" and
      are always flagged.

Usage:
    # Dry run (default) — list keys with lifetime > 90 days
    python delete_long_lived_api_keys.py

    # Same, but with a custom threshold
    python delete_long_lived_api_keys.py --days 30

    # Actually delete the offending keys
    python delete_long_lived_api_keys.py --delete

Environment variables (set in .env file):
    API_KEY            API key (e.g. endr+...)
    API_SECRET         API secret (e.g. endr+...)
    ENDOR_NAMESPACE    Root tenant namespace (children are traversed)
    ENDOR_API_BASE_URL Optional, defaults to https://api.endorlabs.com
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("ENDOR_API_BASE_URL", "https://api.endorlabs.com").rstrip("/")
AUTH_ENDPOINT = f"{BASE_URL}/v1/auth/api-key"

DEFAULT_THRESHOLD_DAYS = 90

EXIT_OK = 0
EXIT_ISSUES_FOUND = 1
EXIT_FAILURE = 2


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def get_token(api_key: str, api_secret: str) -> str:
    """Exchange an API key + secret for a short-lived bearer token."""
    resp = requests.post(
        AUTH_ENDPOINT,
        json={"key": api_key, "secret": api_secret},
        timeout=30,
    )
    if not resp.ok:
        print(
            f"[ERROR] Authentication failed ({resp.status_code}): {resp.text}",
            file=sys.stderr,
        )
        sys.exit(EXIT_FAILURE)

    token = resp.json().get("token")
    if not token:
        print("[ERROR] No token returned by authentication endpoint.", file=sys.stderr)
        sys.exit(EXIT_FAILURE)

    return token


# ---------------------------------------------------------------------------
# API key listing
# ---------------------------------------------------------------------------

def list_api_keys(token: str, namespace: str) -> list[dict]:
    """Fetch all APIKey resources in `namespace` and its descendants."""
    url = f"{BASE_URL}/v1/namespaces/{namespace}/api-keys"
    headers = {"Authorization": f"Bearer {token}"}
    all_keys: list[dict] = []
    page_id: str | None = None

    while True:
        params: dict = {"list_parameters.traverse": "true"}
        if page_id:
            params["list_parameters.page_id"] = page_id

        resp = requests.get(url, headers=headers, params=params, timeout=60)
        if not resp.ok:
            print(
                f"[ERROR] Failed to list API keys ({resp.status_code}): {resp.text}",
                file=sys.stderr,
            )
            sys.exit(EXIT_FAILURE)

        body = resp.json()
        objects = body.get("list", {}).get("objects") or []
        all_keys.extend(objects)

        page_id = body.get("list", {}).get("response", {}).get("next_page_id")
        if not page_id:
            break

    return all_keys


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _parse_dt(raw: str | None) -> datetime | None:
    """Parse an ISO8601 timestamp into a tz-aware UTC datetime."""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def classify_keys(keys: list[dict], threshold_days: int) -> tuple[list[dict], list[dict]]:
    """
    Split keys into:
        offending – lifetime (expiration_time - create_time) > threshold_days,
                    OR no expiration_time set (treated as infinite lifetime)
        compliant – everything else
    Each entry is enriched with human-friendly fields.
    """
    threshold = timedelta(days=threshold_days)
    offending: list[dict] = []
    compliant: list[dict] = []

    for key in keys:
        meta = key.get("meta", {})
        spec = key.get("spec", {})
        tenant_meta = key.get("tenant_meta", {})

        created = _parse_dt(meta.get("create_time"))
        expires = _parse_dt(spec.get("expiration_time"))

        if created and expires:
            lifetime = expires - created
            lifetime_days_str = f"{lifetime.days} days"
            is_offending = lifetime > threshold
        elif not expires:
            lifetime = None
            lifetime_days_str = "no expiration (infinite)"
            is_offending = True
        else:
            # expires set but no create_time — fall back to "now" for reporting
            lifetime = None
            lifetime_days_str = "unknown (missing create_time)"
            is_offending = False

        entry = {
            "uuid": key.get("uuid", ""),
            "name": meta.get("name", "<unnamed>"),
            "namespace": tenant_meta.get("namespace", ""),
            "created_by": meta.get("created_by", ""),
            "email": spec.get("issuing_user", {}).get("spec", {}).get("email", ""),
            "create_time": created.strftime("%Y-%m-%d %H:%M UTC") if created else "unknown",
            "expiration_time": expires.strftime("%Y-%m-%d %H:%M UTC") if expires else "no expiry set",
            "lifetime": lifetime_days_str,
            "_lifetime_td": lifetime,
        }

        if is_offending:
            offending.append(entry)
        else:
            compliant.append(entry)

    # Sort offending: longest lifetime / no-expiry first
    def _sort_key(e: dict) -> tuple[int, int]:
        td = e["_lifetime_td"]
        if td is None:
            return (0, 0)  # no-expiry sorts first
        return (1, -td.days)

    offending.sort(key=_sort_key)
    return offending, compliant


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _row(entry: dict) -> str:
    email = f"  [{entry['email']}]" if entry["email"] else ""
    ns = f"  ({entry['namespace']})" if entry["namespace"] else ""
    return (
        f"  - {entry['name']}{email}{ns}\n"
        f"    UUID       : {entry['uuid']}\n"
        f"    Created    : {entry['create_time']}\n"
        f"    Expires    : {entry['expiration_time']}\n"
        f"    Lifetime   : {entry['lifetime']}\n"
        f"    Owner      : {entry['created_by']}"
    )


def print_report(
    offending: list[dict],
    compliant: list[dict],
    threshold_days: int,
    delete_mode: bool,
) -> None:
    mode = "DELETE" if delete_mode else "DRY-RUN"
    print(f"\n{'=' * 70}")
    print(f"  Endor Labs – Long-Lived API Key {mode} Report")
    print(f"  Generated  : {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Threshold  : lifetime > {threshold_days} days")
    print(f"  Mode       : {mode}{'' if delete_mode else '  (no keys will be deleted; pass --delete to remove)'}")
    print(f"{'=' * 70}\n")

    if offending:
        verb = "WILL BE DELETED" if delete_mode else "WOULD BE DELETED"
        print(f"[FLAGGED] {len(offending)} key(s) {verb}:\n")
        for e in offending:
            print(_row(e))
            print()
    else:
        print(f"[OK] No API keys exceed the {threshold_days}-day lifetime threshold.\n")

    print(f"Summary: {len(offending)} flagged, {len(compliant)} compliant.")
    print(f"{'=' * 70}\n")


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------

def delete_api_key(token: str, namespace: str, uuid: str) -> tuple[bool, str]:
    """Delete a single API key. Returns (ok, message)."""
    if not namespace:
        return False, "missing namespace on key object"
    if not uuid:
        return False, "missing uuid on key object"

    url = f"{BASE_URL}/v1/namespaces/{namespace}/api-keys/{uuid}"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        resp = requests.delete(url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        return False, f"request error: {exc}"

    if resp.ok:
        return True, "deleted"
    return False, f"HTTP {resp.status_code}: {resp.text.strip()[:200]}"


def delete_offending_keys(token: str, offending: list[dict]) -> tuple[int, int]:
    """Delete every key in `offending`. Returns (success_count, failure_count)."""
    if not offending:
        return 0, 0

    print(f"Deleting {len(offending)} flagged API key(s)...\n")
    success = 0
    failure = 0

    for entry in offending:
        ok, msg = delete_api_key(token, entry["namespace"], entry["uuid"])
        label = f"{entry['name']} ({entry['uuid']}) in '{entry['namespace']}'"
        if ok:
            success += 1
            print(f"  [OK]   deleted {label}")
        else:
            failure += 1
            print(f"  [FAIL] {label}: {msg}", file=sys.stderr)

    print(f"\nDeletion summary: {success} deleted, {failure} failed.\n")
    return success, failure


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detect Endor Labs API keys with a lifetime greater than a threshold "
            "(default: 90 days) and optionally delete them. "
            "Defaults to dry-run; pass --delete to actually remove keys."
        ),
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_THRESHOLD_DAYS,
        help=f"Flag keys whose lifetime exceeds this many days (default: {DEFAULT_THRESHOLD_DAYS}).",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually delete the flagged keys. Without this flag the script runs in dry-run mode.",
    )
    parser.add_argument(
        "--namespace",
        default=None,
        help="Override the ENDOR_NAMESPACE env var. The namespace is traversed recursively.",
    )
    parser.add_argument(
        "--json",
        dest="dump_json",
        action="store_true",
        help="Print the raw flagged-key payload as JSON at the end (useful for piping to other tools).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    api_key = os.getenv("API_KEY", "")
    api_secret = os.getenv("API_SECRET", "")
    namespace = args.namespace or os.getenv("ENDOR_NAMESPACE", "")

    missing: list[str] = []
    if not api_key:
        missing.append("API_KEY")
    if not api_secret:
        missing.append("API_SECRET")
    if not namespace:
        missing.append("ENDOR_NAMESPACE (or --namespace)")

    if missing:
        print(
            f"[ERROR] Missing required configuration: {', '.join(missing)}\n"
            "        Set these in your .env file (see .env.example) "
            "or pass --namespace on the CLI.",
            file=sys.stderr,
        )
        sys.exit(EXIT_FAILURE)

    if args.days <= 0:
        print("[ERROR] --days must be a positive integer.", file=sys.stderr)
        sys.exit(EXIT_FAILURE)

    print("Authenticating with Endor Labs API...")
    token = get_token(api_key, api_secret)

    print(f"Fetching API keys for namespace '{namespace}' (traversing children)...")
    keys = list_api_keys(token, namespace)
    print(f"Found {len(keys)} API key(s) in scope.\n")

    offending, compliant = classify_keys(keys, args.days)
    print_report(offending, compliant, args.days, delete_mode=args.delete)

    if args.dump_json:
        print("Flagged keys (JSON):")
        print(json.dumps(
            [{k: v for k, v in e.items() if not k.startswith("_")} for e in offending],
            indent=2,
        ))
        print()

    exit_code = EXIT_OK
    if args.delete and offending:
        _success, failure = delete_offending_keys(token, offending)
        if failure:
            exit_code = EXIT_FAILURE
    elif offending:
        # Dry-run with findings — signal "issues found" so this fits in CI nicely.
        exit_code = EXIT_ISSUES_FOUND

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
