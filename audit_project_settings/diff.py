import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def load_audit(path: str) -> dict:
    """Load and validate a JSON audit file produced by main.py."""
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(1)
    for key in ("meta", "project", "namespaces"):
        if key not in data:
            print(
                f"ERROR: {path} is missing required key '{key}' — is it a valid audit output?",
                file=sys.stderr,
            )
            sys.exit(1)
    return data


def collect_names(audit: dict, resource: str) -> set[str]:
    """Flatten all non-empty names for resource across all namespace levels."""
    names: set[str] = set()
    for ns in audit.get("namespaces", []):
        for item in ns.get(resource, []):
            name = item.get("name", "")
            if name:
                names.add(name)
    return names


def find_missing_policies(audit_a: dict, names_b: set[str]) -> list[dict]:
    """Return policies from A whose names are absent from names_b, deduplicated."""
    missing: list[dict] = []
    seen: set[str] = set()
    for ns in audit_a.get("namespaces", []):
        for policy in ns.get("policies", []):
            name = policy.get("name", "")
            if name and name not in names_b and name not in seen:
                seen.add(name)
                missing.append({
                    "name": name,
                    "policy_type": policy.get("policy_type", ""),
                    "source_namespace": ns.get("namespace", ""),
                    "disabled": policy.get("disabled", False),
                    "url": policy.get("url", ""),
                })
    return missing


def find_missing_profiles(audit_a: dict, names_b: set[str]) -> list[dict]:
    """Return scan profiles from A whose names are absent from names_b, deduplicated."""
    missing: list[dict] = []
    seen: set[str] = set()
    for ns in audit_a.get("namespaces", []):
        for profile in ns.get("scan_profiles", []):
            name = profile.get("name", "")
            if name and name not in names_b and name not in seen:
                seen.add(name)
                missing.append({
                    "name": name,
                    "source_namespace": ns.get("namespace", ""),
                    "is_default": profile.get("is_default", False),
                })
    return missing


def build_result(
    audit_a: dict,
    audit_b: dict,
    missing_policies: list[dict],
    missing_profiles: list[dict],
) -> dict:
    """Assemble the full diff result matching the JSON output schema."""
    def _meta(audit: dict) -> dict:
        return {
            "namespace": audit["meta"]["namespace"],
            "project_name": audit["project"]["name"],
            "project_uuid": audit["project"]["uuid"],
        }
    return {
        "meta": {
            "source_a": _meta(audit_a),
            "source_b": _meta(audit_b),
        },
        "missing_policies": missing_policies,
        "missing_scan_profiles": missing_profiles,
        "summary": {
            "missing_policy_count": len(missing_policies),
            "missing_scan_profile_count": len(missing_profiles),
        },
    }


def format_text(result: dict) -> str:
    """Render the human-readable text summary (no Output: footer)."""
    a = result["meta"]["source_a"]
    b = result["meta"]["source_b"]
    lines = [
        f"Diff: {a['namespace']} ({a['project_uuid']}) → {b['namespace']} ({b['project_uuid']})",
        "",
    ]

    missing_policies = result["missing_policies"]
    policy_count = len(missing_policies)
    if policy_count == 0:
        lines.append("Policies missing from B (0): none")
    else:
        lines.append(f"Policies missing from B ({policy_count}):")
        by_type: dict[str, list[dict]] = {}
        for p in missing_policies:
            by_type.setdefault(p["policy_type"], []).append(p)
        for ptype in sorted(by_type):
            entries = by_type[ptype]
            lines.append(f"  {ptype} ({len(entries)}):")
            for p in entries:
                line = f"    - {p['name']}  [{p['source_namespace']}]"
                if p.get("url"):
                    line += f" {p['url']}"
                lines.append(line)

    lines.append("")

    missing_profiles = result["missing_scan_profiles"]
    profile_count = len(missing_profiles)
    if profile_count == 0:
        lines.append("Scan profiles missing from B (0): none")
    else:
        lines.append(f"Scan profiles missing from B ({profile_count}):")
        for p in missing_profiles:
            lines.append(f"  - {p['name']}  [{p['source_namespace']}]")

    lines.append("")
    p_word = "policy" if policy_count == 1 else "policies"
    s_word = "scan profile" if profile_count == 1 else "scan profiles"
    lines.append(f"Summary: {policy_count} missing {p_word}, {profile_count} missing {s_word}.")
    return "\n".join(lines)


def write_outputs(
    result: dict, text: str, output_dir: str, timestamp: str
) -> tuple[str, str]:
    """Write JSON and text files to output_dir. Creates the dir if needed."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    base = f"diff_audit.{timestamp}"
    json_path = str(Path(output_dir) / f"{base}.json")
    txt_path = str(Path(output_dir) / f"{base}.txt")
    with open(json_path, "w") as f:
        json.dump(result, f, indent=2)
    with open(txt_path, "w") as f:
        f.write(text)
        f.write("\n")
    return json_path, txt_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Diff two audit_project_settings JSON outputs — "
            "shows what A has that B is missing."
        )
    )
    parser.add_argument("audit_a", help="Path to source audit JSON (the reference project)")
    parser.add_argument("audit_b", help="Path to destination audit JSON (the target project)")
    parser.add_argument(
        "--output-dir",
        default="generated_reports",
        help="Directory for output files (default: generated_reports)",
    )
    args = parser.parse_args(argv)

    audit_a = load_audit(args.audit_a)
    audit_b = load_audit(args.audit_b)

    names_b_policies = collect_names(audit_b, "policies")
    names_b_profiles = collect_names(audit_b, "scan_profiles")

    missing_policies = find_missing_policies(audit_a, names_b_policies)
    missing_profiles = find_missing_profiles(audit_a, names_b_profiles)

    result = build_result(audit_a, audit_b, missing_policies, missing_profiles)
    text = format_text(result)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path, txt_path = write_outputs(result, text, args.output_dir, timestamp)

    print(text)
    print(f"\nOutput: {json_path}")
    print(f"        {txt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
