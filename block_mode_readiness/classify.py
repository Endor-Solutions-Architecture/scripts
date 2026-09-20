from __future__ import annotations

from typing import Any, Dict, Optional

_REACHABILITY_TAG_MAP = {
    "FINDING_TAGS_REACHABLE_FUNCTION": "Reachable",
    "FINDING_TAGS_UNREACHABLE_FUNCTION": "Unreachable",
    "FINDING_TAGS_POTENTIALLY_REACHABLE_FUNCTION": "Potentially Reachable",
}


def extract_pr_number(scan: Dict[str, Any]) -> Optional[str]:
    """Extract PR number from context.tags or meta.tags (e.g. 'pr=1')."""
    for tag_source in [
        scan.get("context", {}).get("tags", []),
        scan.get("meta", {}).get("tags", []),
    ]:
        for tag in tag_source:
            if tag.startswith("pr="):
                return tag.split("=", 1)[1]
    return None


def classify_outcome(scan: Dict[str, Any]) -> str:
    spec = scan.get("spec", {}) or {}
    if spec.get("warning_findings"):
        return "warn"
    if spec.get("blocking_findings"):
        return "block"
    return "clean"


def classify_finding(finding: Dict[str, Any]) -> str:
    """Map a Finding object to a short violation type."""
    spec = finding.get("spec", {}) or {}
    cats = spec.get("finding_categories") or []
    tags = spec.get("finding_tags") or []
    if "FINDING_CATEGORY_SECRETS" in cats:
        return "Secrets"
    if "FINDING_CATEGORY_VULNERABILITY" in cats:
        return "Vulnerability"
    if "FINDING_TAGS_AI" in tags:
        return "AI SAST"
    if "FINDING_CATEGORY_SAST" in cats:
        return "SAST"
    return ",".join(cats) or "Unknown"


def derive_fixable(finding_tags: Any) -> str:
    """Return Yes/No fixability label from finding_tags."""
    if not finding_tags:
        return ""
    tags = finding_tags if isinstance(finding_tags, list) else [finding_tags]
    if "FINDING_TAGS_FIX_AVAILABLE" in tags:
        return "Yes"
    if "FINDING_TAGS_UNFIXABLE" in tags:
        return "No"
    return ""


def derive_reachability(finding_tags: Any) -> str:
    """Return a human-readable reachability label from finding_tags."""
    if not finding_tags:
        return ""
    tags = finding_tags if isinstance(finding_tags, list) else [finding_tags]
    for tag in tags:
        label = _REACHABILITY_TAG_MAP.get(tag)
        if label:
            return label
    return ""


def _name_from_policy_item(item: Any) -> Optional[str]:
    if isinstance(item, str):
        return item or None
    if isinstance(item, dict):
        name = item.get("name")
        if isinstance(name, str) and name:
            return name
        meta = item.get("meta") or {}
        meta_name = meta.get("name")
        if isinstance(meta_name, str) and meta_name:
            return meta_name
    return None


def _first_name_from_policy_field(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        for item in value:
            name = _name_from_policy_item(item)
            if name:
                return name
        return ""
    name = _name_from_policy_item(value)
    return name or ""


def extract_policy_name(
    scan: Dict[str, Any],
    policy_names: Optional[Dict[str, str]] = None,
) -> str:
    spec = scan.get("spec", {}) or {}
    policy_name = spec.get("policy_name")
    if isinstance(policy_name, str) and policy_name:
        return policy_name
    for key in ("triggered_policies", "action_policies"):
        name = _first_name_from_policy_field(spec.get(key))
        if name:
            return name
    if policy_names:
        for uuid in spec.get("policies_triggered") or []:
            if isinstance(uuid, str) and uuid in policy_names:
                return policy_names[uuid]
    return ""


def classify_trajectory(
    scan_count: int,
    first_warning_count: int,
    last_warning_count: int,
) -> str:
    if scan_count < 2:
        return "single_scan"
    if last_warning_count < first_warning_count:
        return "acted"
    return "still_open"


def is_cleared(last_warning_count: int, classification: str) -> bool:
    return classification == "acted" and last_warning_count == 0
