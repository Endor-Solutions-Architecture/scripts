#!/usr/bin/env python3
"""
This script will search for projects in the specified namespace AND all its child namespaces to generate a "mega" SBOM for all projects
listed in the .txt file passed into this script as an argument. 
"""
import argparse
import json
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from urllib.parse import unquote

# Default timeout for endorctl subprocess calls (in seconds)
SUBPROCESS_TIMEOUT = 120

# --------------- namespace discovery ---------------

def list_direct_children(namespace_path: str, debug: bool = False) -> List[Tuple[str, str]]:
    """
    List direct child namespaces of the given namespace.
    Makes an API call to the specified namespace to find its children.
    
    Args:
        namespace_path: Full dotted path like 'parent.child.grandchild'
        debug: Enable debug output
    
    Returns a list of tuples: (child_short_name, child_full_path)
    """
    children = []
    
    # Get the short name (last component) for parent matching
    short_name = namespace_path.split(".")[-1] if "." in namespace_path else namespace_path
    
    cmd = [
        "endorctl", "api", "list",
        "-n", namespace_path,
        "-r", "Namespace",
        "--field-mask", "meta.name,tenant_meta.namespace",
        "--page-size", "500",
    ]
    
    try:
        res = subprocess.run(cmd, check=True, text=True, capture_output=True, timeout=SUBPROCESS_TIMEOUT)
        data = json.loads(res.stdout or "{}")
        objs = ((data.get("list") or {}).get("objects") or [])
        
        if debug:
            print(f"    [DEBUG] Querying namespace '{namespace_path}' returned {len(objs)} namespace(s)")
        
        for obj in objs:
            meta = obj.get("meta") or {}
            tenant_meta = obj.get("tenant_meta") or {}
            child_short_name = meta.get("name")
            parent_ns = tenant_meta.get("namespace") or ""
            
            if debug:
                print(f"    [DEBUG]   - '{child_short_name}' has parent '{parent_ns}'")
            
            # Check if this namespace's parent matches (by short name)
            parent_short = parent_ns.split(".")[-1] if "." in parent_ns else parent_ns
            if child_short_name and (parent_ns == namespace_path or parent_ns == short_name or parent_short == short_name):
                # Build full path for child
                child_full_path = f"{namespace_path}.{child_short_name}"
                children.append((child_short_name, child_full_path))
                
    except subprocess.CalledProcessError as e:
        if debug:
            stderr_short = (e.stderr or "")[:200]
            print(f"    [DEBUG] API call to '{namespace_path}' failed: {stderr_short}")
    except subprocess.TimeoutExpired:
        if debug:
            print(f"    [DEBUG] API call to '{namespace_path}' timed out after {SUBPROCESS_TIMEOUT}s")
    except json.JSONDecodeError as e:
        if debug:
            print(f"    [DEBUG] JSON parse error for '{namespace_path}': {e}")
    
    return children


def get_all_descendant_namespaces(parent_namespace: str, max_depth: int = 10, debug: bool = False, max_workers: int = 20) -> List[str]:
    """
    Recursively discover all descendant namespaces (children, grandchildren, etc.) up to max_depth levels.
    Makes recursive API calls to each child namespace using full dotted paths.
    Parallelizes queries within each level for faster discovery.
    Returns a list of all namespace full paths including the parent.
    """
    all_namespaces: List[str] = [parent_namespace]
    visited: Set[str] = {parent_namespace}
    current_level = [parent_namespace]  # Full paths
    depth = 0
    
    while current_level and depth < max_depth:
        next_level = []
        if debug:
            print(f"  [DEBUG] Processing depth {depth + 1}, checking {len(current_level)} namespace(s): {current_level}")
        
        # Parallelize queries within this level
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ns = {executor.submit(list_direct_children, ns_path, debug): ns_path for ns_path in current_level}
            
            for future in as_completed(future_to_ns):
                children = future.result()
                for child_short, child_full in children:
                    if child_full not in visited:
                        visited.add(child_full)
                        all_namespaces.append(child_full)
                        next_level.append(child_full)
                        print(f"  Found child namespace: {child_full} (depth {depth + 1})")
        
        current_level = next_level
        depth += 1
    
    return all_namespaces


# --------------- endorctl helpers ---------------

def run_endorctl_export(namespace: str, project_name: Optional[str] = None, project_uuid: Optional[str] = None) -> dict:
    """
    Export a project-level CycloneDX SBOM via endorctl.
    Prefer UUID if provided for stability.
    Raises RuntimeError with endorctl stderr if the command fails.
    """
    cmd = [
        "endorctl", "sbom", "export",
        "-n", namespace,
        "--component-type", "application",
        "--output-format", "json",
    ]
    if project_uuid:
        cmd += ["--project-uuid", project_uuid, "--app-name", project_uuid]
    elif project_name:
        cmd += ["--project-name", project_name, "--app-name", project_name]
    else:
        raise RuntimeError("run_endorctl_export requires project_uuid or project_name")

    try:
        res = subprocess.run(cmd, check=True, text=True, capture_output=True, timeout=SUBPROCESS_TIMEOUT)
        return json.loads(res.stdout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"endorctl failed for project '{project_uuid or project_name}': {e.stderr}") from e
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"endorctl timed out after {SUBPROCESS_TIMEOUT}s for project '{project_uuid or project_name}'")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from endorctl for '{project_uuid or project_name}': {e}") from e


def resolve_project_uuid_in_namespace(namespace: str, project_name: str) -> str:
    """
    Resolve a Project UUID from a project display name in a specific namespace.
    Strategy:
      1) Exact meta.name == project_name
      2) If it looks like a URL w/o .git, try project_name + '.git'
      3) If name contains URL-encoded chars (e.g., %20), try decoded version
    Returns '' if not found.
    """
    def lookup(name: str) -> str:
        # Quote the name in the filter to handle spaces and special characters
        # Use double quotes inside the filter expression
        filter_expr = f'meta.name=="{name}"'
        cmd = [
            "endorctl", "api", "list",
            "-n", namespace, "-r", "Project",
            "--field-mask", "uuid,meta.name",
            "--filter", filter_expr,
            "--page-size", "1",
        ]
        try:
            res = subprocess.run(cmd, check=True, text=True, capture_output=True, timeout=SUBPROCESS_TIMEOUT)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return ""
        try:
            data = json.loads(res.stdout or "{}")
        except json.JSONDecodeError:
            return ""
        objs = ((data.get("list") or {}).get("objects") or [])
        return (objs[0].get("uuid") if objs else "") or ""

    # Try exact
    uuid_ = lookup(project_name)
    if uuid_:
        return uuid_

    # Heuristic: if looks like git URL and doesn't end in .git
    if project_name.startswith("http") and not project_name.endswith(".git"):
        uuid_ = lookup(project_name + ".git")
        if uuid_:
            return uuid_

    # Heuristic: if name contains URL-encoded characters, try decoded version
    decoded_name = unquote(project_name)
    if decoded_name != project_name:
        uuid_ = lookup(decoded_name)
        if uuid_:
            return uuid_
        # Also try decoded + .git
        if decoded_name.startswith("http") and not decoded_name.endswith(".git"):
            uuid_ = lookup(decoded_name + ".git")
            if uuid_:
                return uuid_

    return ""


def resolve_project_across_namespaces(
    namespaces: List[str], 
    project_name: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    Search for a project across multiple namespaces.
    Returns (namespace, uuid) tuple where the project was found.
    Returns (None, None) if not found in any namespace.
    """
    for ns in namespaces:
        uuid_ = resolve_project_uuid_in_namespace(ns, project_name)
        if uuid_:
            return (ns, uuid_)
    
    return (None, None)


def export_project(
    namespaces: List[str],
    proj_display: str
) -> Tuple[dict, str]:
    """
    Export a project's SBOM.
    Searches across all provided namespaces to find the project.
    - Resolve UUID first; fallback to name if UUID not found.
    - Raises exception on failure (no retries).
    
    Returns (bom_dict, namespace_found_in) tuple.
    """
    # Resolve project across all namespaces
    found_ns, proj_uuid = resolve_project_across_namespaces(namespaces, proj_display)
    
    if not found_ns:
        # Project not found in any namespace - try exporting by name from first namespace as fallback
        found_ns = namespaces[0]
        proj_uuid = None

    if proj_uuid:
        bom = run_endorctl_export(found_ns, project_uuid=proj_uuid)
    else:
        bom = run_endorctl_export(found_ns, project_name=proj_display)
    
    return (bom, found_ns)


# --------------- merge helpers ---------------

def normalize_component_key(c: dict) -> Tuple[str, str, str]:
    """
    Dedup key for components:
    Prefer purl+version; fallback to name+version+type.
    """
    purl = c.get("purl") or ""
    version = c.get("version") or ""
    name = c.get("name") or ""
    ctype = c.get("type") or ""
    if purl:
        return ("purl", purl, version)
    return ("nameverttype", f"{name}@@{version}", ctype)


def unique_bom_ref(existing_refs: Set[str], desired: str) -> str:
    """
    Ensure bom-ref uniqueness by appending a suffix if needed.
    """
    if desired not in existing_refs:
        return desired
    base = desired
    i = 1
    while True:
        candidate = f"{base}__{i}"
        if candidate not in existing_refs:
            return candidate
        i += 1


def merge_boms(boms: List[dict], portfolio_name: str = "Portfolio") -> dict:
    """
    Merge multiple CycloneDX BOMs into a single BOM.
    - Dedupe components
    - Resolve bom-ref collisions
    - Merge dependencies
    - Add portfolio root that depends on each project root
    """
    # Determine highest specVersion found (default 1.4)
    spec_versions = [b.get("specVersion") for b in boms if b.get("specVersion")]
    spec_version = max(spec_versions, default="1.4")

    out = {
        "bomFormat": "CycloneDX",
        "specVersion": spec_version,
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "component": {
                "bom-ref": f"portfolio:{portfolio_name}",
                "type": "application",
                "name": portfolio_name,
            }
        },
        "components": [],
        "dependencies": []
    }

    global_components: Dict[Tuple[str, str, str], dict] = {}
    global_bomrefs: Set[str] = set([out["metadata"]["component"]["bom-ref"]])
    global_ref_deps: Dict[str, Set[str]] = {}  # ref -> set(dependsOn)
    project_root_refs: List[str] = []

    for b in boms:
        comp_list = b.get("components", []) or []
        deps_list = b.get("dependencies", []) or []
        meta_comp = ((b.get("metadata") or {}).get("component") or {})

        # Map from old -> new bom-ref for this BOM
        ref_map: Dict[str, str] = {}

        # Add components
        for c in comp_list:
            key = normalize_component_key(c)

            old_ref = c.get("bom-ref") or ""
            if not old_ref:
                old_ref = f"ref:{key[0]}:{key[1]}:{key[2]}"
                c["bom-ref"] = old_ref

            new_ref = unique_bom_ref(global_bomrefs, old_ref)
            if new_ref != old_ref:
                c = dict(c)
                c["bom-ref"] = new_ref
            ref_map[old_ref] = c["bom-ref"]
            global_bomrefs.add(c["bom-ref"])

            if key not in global_components:
                global_components[key] = c
            else:
                existing = global_components[key]
                # Merge licenses if missing
                if "licenses" not in existing and "licenses" in c:
                    existing["licenses"] = c["licenses"]
                # Merge externalReferences (dedup by url+type)
                if "externalReferences" in c:
                    er = existing.get("externalReferences", [])
                    er2 = c.get("externalReferences", [])
                    if er2:
                        seen = {(x.get("url"), x.get("type")) for x in er}
                        for x in er2:
                            t = (x.get("url"), x.get("type"))
                            if t not in seen:
                                er.append(x)
                                seen.add(t)
                        existing["externalReferences"] = er

        # Merge dependencies; rewrite refs via ref_map
        for d in deps_list:
            old_ref = d.get("ref")
            if not old_ref:
                continue
            new_ref = ref_map.get(old_ref, old_ref)
            depends_on = []
            for dep in d.get("dependsOn", []) or []:
                depends_on.append(ref_map.get(dep, dep))
            if new_ref not in global_ref_deps:
                global_ref_deps[new_ref] = set()
            global_ref_deps[new_ref].update(depends_on)

        # Track project root component bom-ref
        project_root_old = meta_comp.get("bom-ref")
        if project_root_old:
            project_root_refs.append(ref_map.get(project_root_old, project_root_old))

    # Compile components into output
    out["components"] = list(global_components.values())

    # Build dependencies
    out_deps = []
    for ref, deps in global_ref_deps.items():
        out_deps.append({
            "ref": ref,
            "dependsOn": sorted(deps)
        })

    # Link portfolio root to each project root
    portfolio_ref = out["metadata"]["component"]["bom-ref"]
    if project_root_refs:
        out_deps.append({
            "ref": portfolio_ref,
            "dependsOn": sorted(set(project_root_refs))
        })

    out["dependencies"] = out_deps
    return out


# --------------- CLI / main ---------------

def read_projects(path: Path) -> List[str]:
    """Read project names from file, ignoring empty lines and comments (lines starting with #)."""
    lines = []
    for ln in path.read_text().splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            lines.append(ln)
    return lines


def get_failed_projects_filename(output_path: str) -> str:
    """
    Generate a dynamic failed projects filename based on the output SBOM filename.
    Example: 'tsaekao-endor-mega-sbom.json' -> 'tsaekao-endor-failed_projects.txt'
    """
    out_path = Path(output_path)
    stem = out_path.stem  # e.g., 'tsaekao-endor-mega-sbom'
    
    # Remove common suffixes like '-mega-sbom', '-sbom', '_sbom', etc.
    for suffix in ['-mega-sbom', '_mega-sbom', '-mega_sbom', '_mega_sbom', '-sbom', '_sbom']:
        if stem.lower().endswith(suffix):
            stem = stem[:-len(suffix)]
            break
    
    return f"{stem}-failed_projects.txt"


def main():
    parser = argparse.ArgumentParser(
        description="Generate a mega CycloneDX SBOM by exporting and merging projects via endorctl. "
                    "This version traverses child namespaces to find projects."
    )
    parser.add_argument("-n", "--namespace", required=True, help="Parent Endor namespace (will also search child namespaces)")
    parser.add_argument("-p", "--projects-file", required=True, help="Path to projects.txt (one project name per line)")
    parser.add_argument("-o", "--output", default="mega-sbom.cyclonedx.json", help="Output SBOM path")
    parser.add_argument("--portfolio-name", default="Portfolio", help="Name of the synthetic portfolio root component")
    parser.add_argument("--no-child-namespaces", action="store_true", 
                        help="Disable child namespace traversal (use only the specified namespace)")
    parser.add_argument("--max-depth", type=int, default=10, 
                        help="Maximum depth to traverse child namespaces (default 10)")
    parser.add_argument("--workers", type=int, default=20,
                        help="Number of parallel workers for SBOM exports (default 20)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug output for namespace discovery")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Timeout in seconds for each endorctl call (default 120)")
    args = parser.parse_args()
    
    # Update global timeout from CLI argument
    global SUBPROCESS_TIMEOUT
    SUBPROCESS_TIMEOUT = args.timeout

    # Discover namespaces
    if args.no_child_namespaces:
        namespaces = [args.namespace]
        print(f"Child namespace traversal disabled. Using only: {args.namespace}")
    else:
        print(f"Discovering child namespaces under '{args.namespace}'...")
        namespaces = get_all_descendant_namespaces(args.namespace, max_depth=args.max_depth, debug=args.debug, max_workers=args.workers)
        if len(namespaces) == 1:
            print(f"No child namespaces found. Using only: {args.namespace}")
        else:
            print(f"Found {len(namespaces)} namespace(s):")
            for ns in namespaces:
                print(f"    - {ns}")

    projects = read_projects(Path(args.projects_file))
    print(f"Loaded {len(projects)} project(s) from {args.projects_file}")
    if not projects:
        raise SystemExit(f"No projects found. Check the path/filename: {args.projects_file}")

    failed: List[str] = []
    boms: List[dict] = []
    namespace_summary: Dict[str, int] = {}  # Track which namespace each project came from
    
    # Thread-safe counters and locks for parallel execution
    print_lock = threading.Lock()
    results_lock = threading.Lock()
    completed_count = [0]  # Use list for mutable counter in closure

    def export_single_project(proj: str) -> Tuple[str, Optional[dict], Optional[str], Optional[str]]:
        """
        Export a single project's SBOM. Returns (project_name, bom_or_None, namespace_or_None, error_or_None).
        """
        try:
            bom, found_ns = export_project(
                namespaces=namespaces,
                proj_display=proj
            )
            if bom.get("bomFormat") != "CycloneDX":
                raise RuntimeError(f"Unexpected bomFormat for '{proj}': {bom.get('bomFormat')}")
            return (proj, bom, found_ns, None)
        except Exception as e:
            err_msg = str(e)
            err_lines = [ln.strip() for ln in err_msg.splitlines() if ln.strip()]
            short_err = err_lines[-1][:150] if err_lines else err_msg[:150]
            return (proj, None, None, short_err)

    print(f"Exporting CycloneDX SBOMs for {len(projects)} projects with {args.workers} workers...")
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        future_to_proj = {executor.submit(export_single_project, proj): proj for proj in projects}
        
        # Process completed tasks as they finish
        for future in as_completed(future_to_proj):
            proj_name, bom, found_ns, error = future.result()
            
            with results_lock:
                completed_count[0] += 1
                current = completed_count[0]
            
            with print_lock:
                if error:
                    print(f"  [{current}/{len(projects)}] {proj_name} - FAILED: {error}")
                    failed.append(proj_name)
                else:
                    boms.append(bom)
                    namespace_summary[found_ns] = namespace_summary.get(found_ns, 0) + 1
                    if found_ns != args.namespace:
                        print(f"  [{current}/{len(projects)}] {proj_name} (found in: {found_ns})")
                    else:
                        print(f"  [{current}/{len(projects)}] {proj_name}")

    if not boms:
        raise SystemExit("No SBOMs exported. Aborting.")

    # Print namespace distribution summary
    if len(namespace_summary) > 1:
        print("\nNamespace distribution:")
        for ns, count in sorted(namespace_summary.items(), key=lambda x: -x[1]):
            print(f"  {ns}: {count} project(s)")

    if failed:
        failed_filename = get_failed_projects_filename(args.output)
        Path(failed_filename).write_text("\n".join(failed) + "\n")
        print(f"\nCompleted with {len(failed)} failure(s). See {failed_filename}")

    print("\nMerging SBOMs...")
    merged = merge_boms(boms, portfolio_name=args.portfolio_name)

    out_path = Path(args.output)
    out_path.write_text(json.dumps(merged, indent=2))
    print(f"Done. Wrote {out_path}")


if __name__ == "__main__":
    main()
