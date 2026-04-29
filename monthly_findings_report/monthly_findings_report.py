#!/usr/bin/env python3
"""
Generate a consolidated monthly findings report (CSV + optional PDF).

Combines two data sources:
  1. Active findings (from /findings API) created in the target month → Status "Open"
  2. Remediated findings (from /finding-logs API, OPERATION_DELETE) resolved
     in the target month → Status "Fixed"

Default filter: reachable/potentially-reachable, not dismissed.
Override with --custom-filter.

Usage:
    python monthly_findings_report.py --output report.csv
    python monthly_findings_report.py --start-date 2026-03-01 --end-date 2026-03-31 --output report.csv
    python monthly_findings_report.py --output report.csv --project-uuid <uuid>
    python monthly_findings_report.py --output report.csv --project-tags team-alpha,production
    python monthly_findings_report.py --output report.csv --project-tags team-alpha --pdf
    python monthly_findings_report.py --output report.csv --custom-filter "spec.finding_tags contains FINDING_TAGS_NORMAL"
"""

import csv
import os
import re
import sys
import argparse
import calendar
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://api.endorlabs.com/v1"
ENDOR_NAMESPACE = os.getenv("ENDOR_NAMESPACE")

GHSA_PATTERN = re.compile(r"GHSA-[a-zA-Z0-9]+-[a-zA-Z0-9]+-[a-zA-Z0-9]+")
CVE_PATTERN = re.compile(r"CVE-\d{4}-\d+")

# Field mask for active findings
FINDINGS_MASK = (
    "uuid,meta.create_time,meta.description,meta.parent_uuid,"
    "spec.level,spec.finding_tags,spec.finding_categories,"
    "spec.target_dependency_package_name,"
    "spec.ecosystem,spec.project_uuid,tenant_meta.namespace"
)

# Field mask for finding logs (remediated)
FINDING_LOGS_MASK = (
    "uuid,meta.description,meta.parent_uuid,spec.finding_uuid,spec.level,"
    "spec.finding_parent_name,spec.finding_parent_uuid,spec.introduced_at,"
    "spec.resolved_at,spec.days_unresolved,spec.finding_tags,spec.finding_categories,"
    "spec.ecosystem,tenant_meta.namespace"
)

VULNERABILITIES_MASK = "meta.name"
PACKAGE_VERSIONS_MASK = "uuid,spec.relative_path,spec.code_owners.owners"

OUTPUT_COLUMNS = [
    "Project Name",
    "Project URL",
    "CVE ID",
    "Description",
    "Criticality",
    "Status",
    "Package/Application",
    "Package Location",
    "Code Owners",
    "Created At",
    "Resolved At",
    "Days Unresolved",
    "Ecosystem",
    "Reachability",
    "Finding Link",
]

# Default finding filter: reachable, not dismissed
DEFAULT_FINDING_FILTER = (
    "spec.dismiss != true"
    " and spec.finding_tags contains"
    " [FINDING_TAGS_REACHABLE_FUNCTION,FINDING_TAGS_POTENTIALLY_REACHABLE_FUNCTION]"
    " and spec.finding_tags contains"
    " [FINDING_TAGS_REACHABLE_DEPENDENCY,FINDING_TAGS_POTENTIALLY_REACHABLE_DEPENDENCY]"
    " and spec.finding_tags contains [FINDING_TAGS_NORMAL]"
)

_ECOSYSTEM_DISPLAY_MAP = {
    "ECOSYSTEM_APK": "APK",
    "ECOSYSTEM_C": "C/C++",
    "ECOSYSTEM_CARGO": "Rust",
    "ECOSYSTEM_COCOAPOD": "CocoaPods",
    "ECOSYSTEM_DEBIAN": "Debian",
    "ECOSYSTEM_GEM": "Ruby",
    "ECOSYSTEM_GO": "Go",
    "ECOSYSTEM_MAVEN": "Java",
    "ECOSYSTEM_NPM": "JavaScript",
    "ECOSYSTEM_NUGET": ".NET",
    "ECOSYSTEM_PACKAGIST": "PHP",
    "ECOSYSTEM_PYPI": "Python",
    "ECOSYSTEM_RPM": "RPM",
    "ECOSYSTEM_SWIFT": "Swift",
}


def friendly_ecosystem(raw: str) -> str:
    if not raw:
        return ""
    label = _ECOSYSTEM_DISPLAY_MAP.get(raw)
    if label:
        return label
    return raw.replace("ECOSYSTEM_", "").replace("_", " ").title()


def get_token() -> str:
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    if not api_key or not api_secret:
        raise ValueError("API_KEY and API_SECRET must be set in environment")
    url = f"{API_URL}/auth/api-key"
    payload = {"key": api_key, "secret": api_secret}
    headers = {"Content-Type": "application/json", "Request-Timeout": "60"}
    response = requests.post(url, json=payload, headers=headers, timeout=60)
    if response.status_code != 200:
        raise Exception(f"Failed to get token: {response.status_code}, {response.text}")
    token = response.json().get("token")
    if not token:
        raise Exception("No token in API response")
    return token


def parse_date_to_iso(date_str: str, end_of_day: bool = False) -> str:
    dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def get_previous_month_range() -> Tuple[str, str]:
    """Return (start_date, end_date) for the previous calendar month as YYYY-MM-DD strings."""
    today = datetime.now()
    first_of_current = today.replace(day=1)
    last_of_previous = first_of_current - timedelta(days=1)
    first_of_previous = last_of_previous.replace(day=1)
    return first_of_previous.strftime("%Y-%m-%d"), last_of_previous.strftime("%Y-%m-%d")


def paginated_get(
    url: str,
    headers: Dict[str, str],
    params: Dict[str, str],
    page_size: int = 500,
) -> List[Dict[str, Any]]:
    """Generic paginated GET returning all objects."""
    objects: List[Dict[str, Any]] = []
    next_page_id = None
    params["list_parameters.page_size"] = str(page_size)
    while True:
        if next_page_id is not None:
            params["list_parameters.page_id"] = next_page_id
        elif "list_parameters.page_id" in params:
            del params["list_parameters.page_id"]
        response = requests.get(url, headers=headers, params=params, timeout=600)
        if response.status_code != 200:
            print(f"API error ({url}): {response.status_code} - {response.text}", file=sys.stderr)
            raise RuntimeError(f"API call failed: {response.status_code}")
        data = response.json()
        batch = data.get("list", {}).get("objects", [])
        objects.extend(batch)
        next_page_id = data.get("list", {}).get("response", {}).get("next_page_id")
        if not next_page_id:
            break
    return objects


# ── Project resolution ──────────────────────────────────────────────

def fetch_projects_by_tags(
    namespace: str,
    tags: List[str],
    headers: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Fetch projects that match ALL given tags."""
    tag_filters = [f"meta.tags matches '{tag}'" for tag in tags]
    filter_str = " and ".join(tag_filters)
    url = f"{API_URL}/namespaces/{namespace}/projects"
    params = {
        "list_parameters.filter": filter_str,
        "list_parameters.mask": "uuid,meta.name,meta.tags",
    }
    return paginated_get(url, headers, params)


# ── Active findings (Open) ──────────────────────────────────────────

def fetch_active_findings(
    namespace: str,
    start_date: str,
    end_date: str,
    headers: Dict[str, str],
    project_uuid: Optional[str] = None,
    project_uuids: Optional[List[str]] = None,
    custom_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch current active findings created within the date range."""
    start_iso = parse_date_to_iso(start_date)
    end_iso = parse_date_to_iso(end_date, end_of_day=True)
    finding_filter = custom_filter if custom_filter else DEFAULT_FINDING_FILTER
    filters = [
        "context.type==CONTEXT_TYPE_MAIN",
        "spec.finding_categories contains FINDING_CATEGORY_VULNERABILITY",
        f"({finding_filter})",
        f"meta.create_time >= date({start_iso})",
        f"meta.create_time <= date({end_iso})",
    ]
    if project_uuid:
        filters.append(f'spec.project_uuid=="{project_uuid}"')
    elif project_uuids:
        uuid_list = "', '".join(project_uuids)
        filters.append(f"spec.project_uuid in ['{uuid_list}']")
    filter_str = " and ".join(filters)
    url = f"{API_URL}/namespaces/{namespace}/findings"
    params = {
        "list_parameters.filter": filter_str,
        "list_parameters.mask": FINDINGS_MASK,
        "list_parameters.traverse": "true",
    }
    return paginated_get(url, headers, params)


# ── Remediated findings (Fixed) ─────────────────────────────────────

def fetch_remediated_finding_logs(
    namespace: str,
    start_date: str,
    end_date: str,
    headers: Dict[str, str],
    project_uuid: Optional[str] = None,
    project_uuids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Fetch finding logs for findings remediated within the date range."""
    start_iso = parse_date_to_iso(start_date)
    end_iso = parse_date_to_iso(end_date, end_of_day=True)
    filters = [
        "context.type==CONTEXT_TYPE_MAIN",
        "spec.operation==OPERATION_DELETE",
        "spec.finding_categories contains FINDING_CATEGORY_VULNERABILITY",
        "spec.finding_tags contains [FINDING_TAGS_NORMAL]",
        f"meta.create_time >= date({start_iso})",
        f"meta.create_time <= date({end_iso})",
    ]
    if project_uuid:
        filters.append(f'meta.parent_uuid=="{project_uuid}"')
    elif project_uuids:
        uuid_list = "', '".join(project_uuids)
        filters.append(f"meta.parent_uuid in ['{uuid_list}']")
    filter_str = " and ".join(filters)
    url = f"{API_URL}/namespaces/{namespace}/finding-logs"
    params = {
        "list_parameters.filter": filter_str,
        "list_parameters.mask": FINDING_LOGS_MASK,
    }
    return paginated_get(url, headers, params)


# ── Enrichment helpers ───────────────────────────────────────────────

def fetch_package_versions(
    namespace: str,
    uuids: List[str],
    headers: Dict[str, str],
    batch_size: int = 100,
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Fetch relative_path and code_owners for package version UUIDs."""
    relative_paths: Dict[str, str] = {}
    code_owners_map: Dict[str, str] = {}
    if not uuids:
        return relative_paths, code_owners_map
    url = f"{API_URL}/namespaces/{namespace}/package-versions"
    for i in range(0, len(uuids), batch_size):
        batch = uuids[i : i + batch_size]
        uuid_list = "', '".join(batch)
        filter_str = f"uuid in ['{uuid_list}']"
        params = {
            "list_parameters.filter": filter_str,
            "list_parameters.mask": PACKAGE_VERSIONS_MASK,
        }
        for obj in paginated_get(url, headers, dict(params)):
            uid = obj.get("uuid")
            if not uid:
                continue
            spec = obj.get("spec") or {}
            rel_path = spec.get("relative_path") or ""
            relative_paths[uid] = rel_path.strip() if isinstance(rel_path, str) else str(rel_path)
            co_obj = spec.get("code_owners") or {}
            owners = co_obj.get("owners")
            if owners is None:
                code_owners_map[uid] = ""
            elif isinstance(owners, list):
                code_owners_map[uid] = ", ".join(str(x) for x in owners)
            else:
                code_owners_map[uid] = str(owners)
    return relative_paths, code_owners_map


_REACHABILITY_TAG_MAP = {
    "FINDING_TAGS_REACHABLE_FUNCTION": "Reachable",
    "FINDING_TAGS_UNREACHABLE_FUNCTION": "Unreachable",
    "FINDING_TAGS_POTENTIALLY_REACHABLE_FUNCTION": "Potentially Reachable",
}


def derive_fixable(tags: Any) -> str:
    if not tags:
        return ""
    tag_list = tags if isinstance(tags, list) else [tags]
    if "FINDING_TAGS_FIX_AVAILABLE" in tag_list:
        return "Yes"
    if "FINDING_TAGS_UNFIXABLE" in tag_list:
        return "No"
    return ""


def derive_reachability(tags: Any) -> str:
    if not tags:
        return ""
    tag_list = tags if isinstance(tags, list) else [tags]
    for t in tag_list:
        label = _REACHABILITY_TAG_MAP.get(t)
        if label:
            return label
    return ""


def format_list_field(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, list):
        return ", ".join(str(x) for x in val)
    return str(val)


def extract_ghsa_id(description: str) -> Optional[str]:
    if not description or description == "missing":
        return None
    match = GHSA_PATTERN.search(description)
    return match.group(0) if match else None


def extract_cve_id(description: str) -> Optional[str]:
    if not description or description == "missing":
        return None
    match = CVE_PATTERN.search(description)
    return match.group(0) if match else None


def fetch_cve(
    ghsa_id: str,
    headers: Dict[str, str],
    namespace: str = "oss",
) -> Optional[str]:
    url = f"{API_URL}/namespaces/{namespace}/queries/vulnerabilities"
    payload = {
        "meta": {"name": f"ListVulnerabilitiesQuery(namespace:{namespace})"},
        "spec": {
            "vulnerability_name_query": {"name": ghsa_id},
            "mask": VULNERABILITIES_MASK,
        },
    }
    response = requests.post(
        url,
        headers={**headers, "Content-Type": "application/json", "Accept": "application/json"},
        json=payload,
        timeout=60,
    )
    if response.status_code != 200:
        return None
    data = response.json()
    objects = (data.get("response") or {}).get("list", {}).get("objects", [])
    if not objects:
        return None
    return (objects[0].get("meta") or {}).get("name")


# ── Row building ─────────────────────────────────────────────────────

def resolve_cve_id(desc_str: str, ghsa_to_cve: Dict[str, str]) -> str:
    cve = extract_cve_id(desc_str)
    if cve:
        return cve
    ghsa = extract_ghsa_id(desc_str)
    if ghsa:
        return ghsa_to_cve.get(ghsa, ghsa)
    return "missing"


def build_rows_from_active_findings(
    findings: List[Dict[str, Any]],
    namespace: str,
    pkg_paths: Dict[str, str],
    pkg_owners: Dict[str, str],
    ghsa_to_cve: Dict[str, str],
    project_names: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Build output rows from active (open) findings."""
    rows = []
    for obj in findings:
        meta = obj.get("meta") or {}
        spec = obj.get("spec") or {}

        desc = meta.get("description")
        desc_str = desc if desc is not None and str(desc).strip() else "missing"
        parent_uuid = meta.get("parent_uuid") or ""
        project_uuid = spec.get("project_uuid", "")
        finding_uuid = obj.get("uuid", "")

        rows.append({
            "Project Name": (project_names or {}).get(project_uuid, ""),
            "Project URL": f"https://app.endorlabs.com/t/{namespace}/projects/{project_uuid}" if project_uuid else "",
            "CVE ID": resolve_cve_id(desc_str, ghsa_to_cve),
            "Description": desc_str,
            "Criticality": spec.get("level", ""),
            "Status": "Open",
            "Package/Application": spec.get("target_dependency_package_name", ""),
            "Package Location": pkg_paths.get(parent_uuid, "") or "Not Available",
            "Code Owners": pkg_owners.get(parent_uuid, "") or "Not Available",
            "Created At": meta.get("create_time", ""),
            "Resolved At": "",
            "Days Unresolved": "",
            "Ecosystem": friendly_ecosystem(spec.get("ecosystem", "")),
            "Reachability": derive_reachability(spec.get("finding_tags")),
            "Finding Link": f"https://app.endorlabs.com/t/{namespace}/findings/{finding_uuid}" if finding_uuid else "",
        })
    return rows


def build_rows_from_finding_logs(
    logs: List[Dict[str, Any]],
    namespace: str,
    pkg_paths: Dict[str, str],
    pkg_owners: Dict[str, str],
    ghsa_to_cve: Dict[str, str],
    project_names: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Build output rows from remediated finding logs (fixed)."""
    rows = []
    for obj in logs:
        meta = obj.get("meta") or {}
        spec = obj.get("spec") or {}

        desc = meta.get("description")
        desc_str = desc if desc is not None and str(desc).strip() else "missing"
        parent_uuid = spec.get("finding_parent_uuid") or ""
        project_uuid = meta.get("parent_uuid", "")
        finding_uuid = spec.get("finding_uuid", "")

        rows.append({
            "Project Name": (project_names or {}).get(project_uuid, ""),
            "Project URL": f"https://app.endorlabs.com/t/{namespace}/projects/{project_uuid}" if project_uuid else "",
            "CVE ID": resolve_cve_id(desc_str, ghsa_to_cve),
            "Description": desc_str,
            "Criticality": spec.get("level", ""),
            "Status": "Fixed",
            "Package/Application": spec.get("finding_parent_name", ""),
            "Package Location": pkg_paths.get(parent_uuid, "") or "Not Available",
            "Code Owners": pkg_owners.get(parent_uuid, "") or "Not Available",
            "Created At": spec.get("introduced_at", ""),
            "Resolved At": spec.get("resolved_at", ""),
            "Days Unresolved": format_list_field(spec.get("days_unresolved")),
            "Ecosystem": friendly_ecosystem(spec.get("ecosystem", "")),
            "Reachability": derive_reachability(spec.get("finding_tags")),
            "Finding Link": f"https://app.endorlabs.com/t/{namespace}/findings/{finding_uuid}" if finding_uuid else "",
        })
    return rows


def collect_ghsa_lookups(
    objects: List[Dict[str, Any]],
    headers: Dict[str, str],
    ghsa_to_cve: Dict[str, str],
) -> None:
    """Populate ghsa_to_cve cache for any descriptions that have GHSA but no CVE."""
    for obj in objects:
        desc = (obj.get("meta") or {}).get("description")
        desc_str = desc if desc is not None and str(desc).strip() else "missing"
        if extract_cve_id(desc_str):
            continue
        ghsa = extract_ghsa_id(desc_str)
        if ghsa and ghsa not in ghsa_to_cve:
            cve = fetch_cve(ghsa, headers)
            ghsa_to_cve[ghsa] = cve if cve else ""


def write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ── PDF report ──────────────────────────────────────────────────────

_BRAND = {
    "green": "#00D26A",
    "dark": "#1A1A2E",
    "text_primary": "#1A1A2E",
    "text_secondary": "#5A6577",
    "white": "#FFFFFF",
    "table_header_bg": "#1A1A2E",
    "table_header_text": "#FFFFFF",
    "table_row_alt": "#F8F9FA",
    "table_border": "#DEE2E6",
    "critical": "#7B2D26",
    "high": "#C4532D",
    "medium": "#E8963F",
    "low": "#F0C75E",
}

_SEVERITY_ORDER = [
    "FINDING_LEVEL_CRITICAL",
    "FINDING_LEVEL_HIGH",
    "FINDING_LEVEL_MEDIUM",
    "FINDING_LEVEL_LOW",
]

_SEVERITY_LABELS = {
    "FINDING_LEVEL_CRITICAL": "Critical",
    "FINDING_LEVEL_HIGH": "High",
    "FINDING_LEVEL_MEDIUM": "Medium",
    "FINDING_LEVEL_LOW": "Low",
}

_SEVERITY_COLORS = {
    "Critical": _BRAND["critical"],
    "High": _BRAND["high"],
    "Medium": _BRAND["medium"],
    "Low": _BRAND["low"],
}


def _fig_to_rl_image(fig, width: float, height: float):
    from io import BytesIO
    from reportlab.platypus import Image as RLImage
    import matplotlib.pyplot as plt

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return RLImage(buf, width=width, height=height)


def _build_severity_chart(open_rows, fixed_rows, page_width: float):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    severities = ["Critical", "High", "Medium", "Low"]
    open_counts = []
    fixed_counts = []
    for sev in severities:
        raw = next((k for k, v in _SEVERITY_LABELS.items() if v == sev), "")
        open_counts.append(sum(1 for r in open_rows if r.get("Criticality") == raw))
        fixed_counts.append(sum(1 for r in fixed_rows if r.get("Criticality") == raw))

    has_open = any(c > 0 for c in open_counts)
    has_fixed = any(c > 0 for c in fixed_counts)

    x = np.arange(len(severities))
    fig, ax = plt.subplots(figsize=(page_width / 72, 2.8))
    fig.set_facecolor(_BRAND["white"])
    ax.set_facecolor(_BRAND["white"])

    sev_colors = [_SEVERITY_COLORS[s] for s in severities]
    all_bars = []

    if has_open and has_fixed:
        bar_width = 0.35
        all_bars.append(ax.bar(x - bar_width / 2, open_counts, bar_width,
                               label="Open", color=sev_colors, edgecolor="none"))
        all_bars.append(ax.bar(x + bar_width / 2, fixed_counts, bar_width,
                               label="Fixed", color=[_BRAND["green"]] * 4,
                               edgecolor="none", alpha=0.7))
    elif has_open:
        bar_width = 0.5
        all_bars.append(ax.bar(x, open_counts, bar_width,
                               color=sev_colors, edgecolor="none"))
    elif has_fixed:
        bar_width = 0.5
        all_bars.append(ax.bar(x, fixed_counts, bar_width,
                               color=sev_colors, edgecolor="none"))

    for bars in all_bars:
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, h + 0.3, str(int(h)),
                        ha="center", va="bottom", fontsize=8, color=_BRAND["text_secondary"])

    ax.set_xticks(x)
    ax.set_xticklabels(severities)
    ax.set_ylabel("Count", fontsize=9, color=_BRAND["text_secondary"])
    if has_open and has_fixed:
        ax.legend(fontsize=8, frameon=False)
    ax.grid(axis="y", linestyle="-", alpha=0.15, color="#AAAAAA")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#DDDDDD")
    ax.spines["bottom"].set_color("#DDDDDD")
    ax.tick_params(colors=_BRAND["text_secondary"], labelsize=8)
    fig.tight_layout()
    return _fig_to_rl_image(fig, page_width, 2.8 * 72)


def _build_reachability_donut(rows, page_width: float):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    counts = {}
    for r in rows:
        reach = r.get("Reachability") or "Unknown"
        counts[reach] = counts.get(reach, 0) + 1

    if not counts:
        return None

    labels = list(counts.keys())
    values = list(counts.values())
    color_map = {
        "Reachable": _BRAND["critical"],
        "Potentially Reachable": _BRAND["medium"],
        "Unreachable": _BRAND["green"],
        "Unknown": "#AAAAAA",
    }
    colors = [color_map.get(l, "#AAAAAA") for l in labels]

    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    fig.set_facecolor(_BRAND["white"])
    ax.set_facecolor(_BRAND["white"])
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, colors=colors, autopct="%1.0f%%",
        wedgeprops=dict(width=0.4, edgecolor=_BRAND["white"], linewidth=2),
        pctdistance=0.78, textprops={"fontsize": 8},
    )
    for t in autotexts:
        t.set_fontsize(7)
        t.set_color(_BRAND["white"])
    total = sum(values)
    ax.text(0, 0, str(total), ha="center", va="center", fontsize=16,
            fontweight="bold", color=_BRAND["text_primary"])
    ax.text(0, -0.15, "total", ha="center", va="center", fontsize=8,
            color=_BRAND["text_secondary"])
    fig.tight_layout()
    return _fig_to_rl_image(fig, 3.5 * 72, 2.8 * 72)


def write_pdf(
    rows: List[Dict[str, Any]],
    namespace: str,
    start_date: str,
    end_date: str,
    filename: str,
) -> None:
    """Generate a branded PDF report with summary, charts, and split tables."""
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    open_rows = [r for r in rows if r.get("Status") == "Open"]
    fixed_rows = [r for r in rows if r.get("Status") == "Fixed"]

    page_w, page_h = landscape(letter)
    margin = 0.6 * inch
    usable_width = page_w - 2 * margin
    doc = SimpleDocTemplate(filename, pagesize=landscape(letter),
                            leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=margin)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Title2", parent=styles["Title"],
                              fontSize=20, textColor=HexColor(_BRAND["dark"]), spaceAfter=4))
    styles.add(ParagraphStyle("Subtitle", parent=styles["Normal"],
                              fontSize=10, textColor=HexColor(_BRAND["text_secondary"]),
                              spaceAfter=12))
    styles.add(ParagraphStyle("SectionHeader", parent=styles["Heading2"],
                              fontSize=13, textColor=HexColor(_BRAND["dark"]),
                              spaceBefore=16, spaceAfter=8))
    styles.add(ParagraphStyle("CellText", parent=styles["Normal"], fontSize=6, leading=8))

    elements = []

    # ── Header ─────────────────────────────────────────────────────
    elements.append(Paragraph("Monthly Findings Report", styles["Title2"]))
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elements.append(Paragraph(
        f"Namespace: {namespace}  |  Period: {start_date} to {end_date}  |  Generated: {ts}",
        styles["Subtitle"]))

    divider = Table([[""]], colWidths=[usable_width], rowHeights=[3])
    divider.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), HexColor(_BRAND["green"]))]))
    elements.append(divider)
    elements.append(Spacer(1, 12))

    # ── Summary table ─────────────────────────────────────────────
    def _sev_count(row_list, sev_key):
        return sum(1 for r in row_list if r.get("Criticality") == sev_key)

    def _reach_count(row_list, label):
        return sum(1 for r in row_list if r.get("Reachability") == label)

    summary_headers = [
        "", "Total", "Critical", "High", "Medium", "Low",
        "Reachable", "Potentially Reachable",
    ]
    open_summary = [
        "Open",
        str(len(open_rows)),
        str(_sev_count(open_rows, "FINDING_LEVEL_CRITICAL")),
        str(_sev_count(open_rows, "FINDING_LEVEL_HIGH")),
        str(_sev_count(open_rows, "FINDING_LEVEL_MEDIUM")),
        str(_sev_count(open_rows, "FINDING_LEVEL_LOW")),
        str(_reach_count(open_rows, "Reachable")),
        str(_reach_count(open_rows, "Potentially Reachable")),
    ]
    fixed_summary = [
        "Fixed",
        str(len(fixed_rows)),
        str(_sev_count(fixed_rows, "FINDING_LEVEL_CRITICAL")),
        str(_sev_count(fixed_rows, "FINDING_LEVEL_HIGH")),
        str(_sev_count(fixed_rows, "FINDING_LEVEL_MEDIUM")),
        str(_sev_count(fixed_rows, "FINDING_LEVEL_LOW")),
        str(_reach_count(fixed_rows, "Reachable")),
        str(_reach_count(fixed_rows, "Potentially Reachable")),
    ]

    n_cols = len(summary_headers)
    col_w = usable_width / n_cols
    summary_table = Table(
        [summary_headers, open_summary, fixed_summary],
        colWidths=[col_w] * n_cols,
        rowHeights=[20, 28, 28],
    )
    summary_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor(_BRAND["text_secondary"])),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (0, -1), 10),
        ("FONTNAME", (1, 1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (1, 1), (-1, -1), 16),
        ("TEXTCOLOR", (1, 1), (-1, -1), HexColor(_BRAND["text_primary"])),
        ("BACKGROUND", (0, 0), (-1, -1), HexColor(_BRAND["table_row_alt"])),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor(_BRAND["table_border"])),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, HexColor(_BRAND["table_border"])),
        ("LINEBELOW", (0, 1), (-1, 1), 0.5, HexColor(_BRAND["table_border"])),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 12))

    # ── PDF table columns (no Status column) ───────────────────────
    pdf_open_cols = [
        "Project Name", "CVE ID", "Description", "Criticality",
        "Package/Application", "Package Location", "Code Owners",
        "Created At", "Ecosystem", "Reachability", "Finding Link",
    ]
    pdf_fixed_cols = [
        "Project Name", "CVE ID", "Description", "Criticality",
        "Package/Application", "Package Location", "Code Owners",
        "Created At", "Resolved At", "Days Unresolved",
        "Ecosystem", "Reachability", "Finding Link",
    ]

    def _build_detail_table(row_data, columns, table_width):
        n = len(columns)
        col_widths = [table_width / n] * n
        header = [Paragraph(f"<b>{c}</b>", styles["CellText"]) for c in columns]
        data_rows = [header]
        for r in row_data:
            data_rows.append([
                Paragraph(str(r.get(c, "")), styles["CellText"]) for c in columns
            ])
        t = Table(data_rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor(_BRAND["table_header_bg"])),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor(_BRAND["table_header_text"])),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 6),
            ("FONTSIZE", (0, 1), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor(_BRAND["table_border"])),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [HexColor(_BRAND["white"]), HexColor(_BRAND["table_row_alt"])]),
        ]))
        return t

    # ── Open findings section: charts + table ─────────────────────
    if open_rows:
        elements.append(Paragraph(f"Open Findings ({len(open_rows)})", styles["SectionHeader"]))
        elements.append(_build_severity_chart(open_rows, [], usable_width))
        elements.append(Spacer(1, 8))
        donut = _build_reachability_donut(open_rows, usable_width)
        if donut:
            elements.append(Paragraph("Reachability", styles["SectionHeader"]))
            elements.append(donut)
            elements.append(Spacer(1, 8))
        elements.append(_build_detail_table(open_rows, pdf_open_cols, usable_width))
        elements.append(Spacer(1, 12))

    # ── Fixed findings section: charts + table ────────────────────
    if fixed_rows:
        elements.append(Paragraph(f"Fixed Findings ({len(fixed_rows)})", styles["SectionHeader"]))
        elements.append(_build_severity_chart([], fixed_rows, usable_width))
        elements.append(Spacer(1, 8))
        donut = _build_reachability_donut(fixed_rows, usable_width)
        if donut:
            elements.append(Paragraph("Reachability", styles["SectionHeader"]))
            elements.append(donut)
            elements.append(Spacer(1, 8))
        elements.append(_build_detail_table(fixed_rows, pdf_fixed_cols, usable_width))

    doc.build(elements)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a consolidated monthly findings report (open + fixed)."
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Report start date (YYYY-MM-DD). Defaults to first day of previous month.",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="Report end date (YYYY-MM-DD). Defaults to last day of previous month.",
    )
    parser.add_argument("--output", required=True, help="Output CSV file path.")
    project_group = parser.add_mutually_exclusive_group()
    project_group.add_argument(
        "--project-uuid",
        default=None,
        help="Optional project UUID to filter findings to a single project.",
    )
    project_group.add_argument(
        "--project-tags",
        default=None,
        help="Comma-separated project tags. Projects matching ALL tags are included.",
    )
    parser.add_argument(
        "--custom-filter",
        default=None,
        help="Custom finding filter expression. Overrides the default reachable/dismiss filter.",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        default=False,
        help="Generate a PDF report alongside the CSV.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of package_version UUIDs per API request (default: 100).",
    )
    args = parser.parse_args()

    # Default to previous month if dates not provided
    if args.start_date is None or args.end_date is None:
        default_start, default_end = get_previous_month_range()
        if args.start_date is None:
            args.start_date = default_start
        if args.end_date is None:
            args.end_date = default_end

    # Validate dates
    for label, val in [("--start-date", args.start_date), ("--end-date", args.end_date)]:
        try:
            datetime.strptime(val.strip(), "%Y-%m-%d")
        except ValueError:
            print(f"{label} must be YYYY-MM-DD format, got: {val}", file=sys.stderr)
            sys.exit(1)

    if args.start_date > args.end_date:
        print("--start-date must be <= --end-date", file=sys.stderr)
        sys.exit(1)

    if not ENDOR_NAMESPACE:
        print("ENDOR_NAMESPACE must be set in environment", file=sys.stderr)
        sys.exit(1)

    token = os.getenv("ENDOR_API_TOKEN")
    if not token:
        try:
            token = get_token()
        except Exception as e:
            print("Set ENDOR_API_TOKEN or both API_KEY and API_SECRET in environment.", file=sys.stderr)
            print(f"Auth failed: {e}", file=sys.stderr)
            sys.exit(1)

    headers = {
        "User-Agent": "curl/7.68.0",
        "Accept": "*/*",
        "Authorization": f"Bearer {token}",
        "Request-Timeout": "600",
    }

    print(f"Report period: {args.start_date} to {args.end_date}")

    # ── Resolve project scope ──────────────────────────────────────
    project_uuids: Optional[List[str]] = None
    project_names: Dict[str, str] = {}

    if args.project_uuid:
        print(f"  Filtering by project: {args.project_uuid}")
    elif args.project_tags:
        tags = [t.strip() for t in args.project_tags.split(",") if t.strip()]
        print(f"  Resolving projects matching tags: {tags}")
        projects = fetch_projects_by_tags(ENDOR_NAMESPACE, tags, headers)
        if not projects:
            print("No projects found matching the given tags.", file=sys.stderr)
            sys.exit(1)
        project_uuids = [p.get("uuid") for p in projects if p.get("uuid")]
        project_names = {
            p.get("uuid", ""): (p.get("meta") or {}).get("name", "")
            for p in projects if p.get("uuid")
        }
        print(f"  Found {len(project_uuids)} projects: {', '.join(project_names.values())}")

    # ── Fetch data from both sources ────────────────────────────────
    if args.custom_filter:
        print(f"  Using custom filter: {args.custom_filter}")

    print("Fetching active (open) findings created in period...")
    active_findings = fetch_active_findings(
        ENDOR_NAMESPACE, args.start_date, args.end_date, headers,
        project_uuid=args.project_uuid, project_uuids=project_uuids,
        custom_filter=args.custom_filter,
    )
    print(f"  Found {len(active_findings)} open findings")

    print("Fetching remediated (fixed) finding logs in period...")
    remediated_logs = fetch_remediated_finding_logs(
        ENDOR_NAMESPACE, args.start_date, args.end_date, headers,
        project_uuid=args.project_uuid, project_uuids=project_uuids,
    )
    print(f"  Found {len(remediated_logs)} fixed findings")

    if not active_findings and not remediated_logs:
        write_csv(args.output, [])
        print(f"No findings found. Wrote empty report to {args.output}")
        return

    # ── Collect package version UUIDs for enrichment ────────────────
    pv_uuids = set()
    for obj in active_findings:
        pv = (obj.get("meta") or {}).get("parent_uuid")
        if pv:
            pv_uuids.add(pv)
    for obj in remediated_logs:
        pv = (obj.get("spec") or {}).get("finding_parent_uuid")
        if pv:
            pv_uuids.add(pv)

    pkg_paths: Dict[str, str] = {}
    pkg_owners: Dict[str, str] = {}
    if pv_uuids:
        print(f"Fetching package version data for {len(pv_uuids)} packages...")
        pkg_paths, pkg_owners = fetch_package_versions(
            ENDOR_NAMESPACE, list(pv_uuids), headers, batch_size=args.batch_size
        )

    # ── Resolve GHSA → CVE lookups ──────────────────────────────────
    ghsa_to_cve: Dict[str, str] = {}
    print("Resolving CVE IDs...")
    collect_ghsa_lookups(active_findings, headers, ghsa_to_cve)
    collect_ghsa_lookups(remediated_logs, headers, ghsa_to_cve)

    # ── Build consolidated rows ─────────────────────────────────────
    rows = build_rows_from_active_findings(
        active_findings, ENDOR_NAMESPACE, pkg_paths, pkg_owners, ghsa_to_cve, project_names,
    )
    rows.extend(build_rows_from_finding_logs(
        remediated_logs, ENDOR_NAMESPACE, pkg_paths, pkg_owners, ghsa_to_cve, project_names,
    ))

    # Sort by Created At (oldest first)
    rows.sort(key=lambda r: r.get("Created At") or "")

    write_csv(args.output, rows)
    open_count = sum(1 for r in rows if r["Status"] == "Open")
    fixed_count = sum(1 for r in rows if r["Status"] == "Fixed")
    print(f"Wrote {len(rows)} rows to {args.output} ({open_count} open, {fixed_count} fixed)")

    if args.pdf:
        pdf_path = os.path.splitext(args.output)[0] + ".pdf"
        write_pdf(rows, ENDOR_NAMESPACE, args.start_date, args.end_date, pdf_path)
        print(f"PDF report generated: {pdf_path}")


if __name__ == "__main__":
    main()
