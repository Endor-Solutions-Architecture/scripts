"""Pure computation for the AI SAST tier recommender.

No Streamlit or subprocess dependencies here — keeps this module fast and
easy to unit test in isolation. All I/O (endorctl, Streamlit) lives in
dashboard.py; all decision logic lives here.

The design is asymmetric on purpose (see the design spec, §3):
  - VALUE signals are per-repo and high fidelity (languages, activity,
    findings, monitored versions).
  - COST is coarse: AICreditMetric spend is only available aggregated at the
    tenant/day/model level (no per-feature, no per-repo attribution), so the
    cost model is a single global $/KLOC rate scaled by repo size, with an
    honest confidence flag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

# --- Language support (mirrors codeapi.SupportedLanguages: the 12 AI SAST langs) ---

SUPPORTED_LANGUAGES: frozenset[str] = frozenset(
    {"c", "cpp", "csharp", "go", "java", "javascript", "python", "ruby", "rust", "scala", "swift", "typescript"}
)

# Maps the many spellings ingested from SCMs (GitHub-style names, enum-ish
# variants) onto the canonical tokens above.
_LANGUAGE_ALIASES: dict[str, str] = {
    "c": "c",
    "c++": "cpp",
    "cpp": "cpp",
    "c#": "csharp",
    "csharp": "csharp",
    "cs": "csharp",
    "go": "go",
    "golang": "go",
    "java": "java",
    "javascript": "javascript",
    "js": "javascript",
    "node": "javascript",
    "python": "python",
    "py": "python",
    "ruby": "ruby",
    "rb": "ruby",
    "rust": "rust",
    "rs": "rust",
    "scala": "scala",
    "swift": "swift",
    "typescript": "typescript",
    "ts": "typescript",
}

# --- Tunable defaults (all overridable from the UI) ---

LANGUAGE_GATE_THRESHOLD: float = 0.50  # min supported-language byte share for Tier 1/2 eligibility
SAFETY_MARGIN: float = 0.20            # reserve 20% of the pool as headroom
MONITORED_VERSION_K: float = 0.30      # each extra monitored version adds k of a baseline
AVG_BYTES_PER_LINE: float = 30.0       # bytes -> LOC conversion for the size proxy
PER_FINDING_TIER2_COST: float = 0.02   # heuristic $/finding for Tier-2 FP triage (NOT calibrated; see §5.4)

DEFAULT_WEIGHTS: dict[str, float] = {"activity": 1 / 3, "findings": 1 / 3, "release": 1 / 3}

# Size-bucket fallback ($ per repo) used when no cost calibration is available.
SIZE_BUCKETS: list[tuple[float, float]] = [
    (10.0, 2.0),     # <10 KLOC  -> ~$2
    (50.0, 6.0),     # <50 KLOC  -> ~$6
    (200.0, 20.0),   # <200 KLOC -> ~$20
]
SIZE_BUCKET_LARGE_COST: float = 50.0   # >= largest threshold


def normalize_language(name: str) -> Optional[str]:
    """Canonical supported-language token for an ingested language name, or None if unsupported."""
    token = _LANGUAGE_ALIASES.get(name.strip().lower())
    return token if token in SUPPORTED_LANGUAGES else None


def root_namespace(namespace: str) -> str:
    """Tenant root (first path segment) of a namespace.

    AICreditMetric is a root-only, non-local resource — it's written and read at
    'namespace.Root(...)' and never surfaces from a child/app namespace via
    traversal. Spend calibration must therefore query the root, not the child.
    'acme-corp.acme-appdev' -> 'acme-corp'.
    """
    return namespace.split(".")[0] if namespace else namespace


def short_repo_name(name: str) -> str:
    """Last path segment of a repo URL/name, without a trailing '.git' (for legible display).

    'https://github.com/acme-platform/pr-agent-settings.git' -> 'pr-agent-settings'.
    Falls back to the original string if there's nothing to trim.
    """
    if not name:
        return name
    segment = name.rstrip("/").rsplit("/", 1)[-1]
    if segment.endswith(".git"):
        segment = segment[:-4]
    return segment or name


def supported_language_share(languages: dict[str, float]) -> float:
    """Fraction of bytes written in AI-SAST-supported languages. 0.0 for an empty/None map."""
    if not languages:
        return 0.0
    total = 0.0
    supported = 0.0
    for name, byte_count in languages.items():
        b = float(byte_count or 0)
        total += b
        if normalize_language(name) is not None:
            supported += b
    if total <= 0:
        return 0.0
    return supported / total


def passes_language_gate(share: float, threshold: float = LANGUAGE_GATE_THRESHOLD) -> bool:
    """True when a repo has enough supported-language code to make AI SAST worthwhile."""
    return share >= threshold


def supported_kloc(languages: dict[str, float], bytes_per_line: float = AVG_BYTES_PER_LINE) -> float:
    """Approximate thousands-of-lines-of-code in supported languages (size/cost proxy)."""
    if not languages or bytes_per_line <= 0:
        return 0.0
    supported_bytes = sum(
        float(b or 0) for name, b in languages.items() if normalize_language(name) is not None
    )
    return supported_bytes / bytes_per_line / 1000.0


def total_supported_kloc(languages_maps: list[dict[str, float]]) -> float:
    """Combined supported-language KLOC across a set of repos (their language maps).

    Used to derive the calibration denominator from the repos a CSE has already
    baselined — no manual KLOC entry needed, since repo sizes come from the
    language data the tool already fetched.
    """
    return sum(supported_kloc(m) for m in languages_maps)


def calibrate_cost_per_kloc(total_spend: float, total_scanned_kloc: float) -> tuple[Optional[float], str]:
    """Global blended $/KLOC from observed spend, with a confidence label.

    Returns (rate, confidence). rate is None when there is no calibration data,
    in which case callers must fall back to size buckets. Confidence is coarse
    because spend is only a tenant-wide aggregate (see spec §3):
      - "none":   no scanned KLOC yet -> use size buckets.
      - "low":    some data but a small sample.
      - "medium": a more substantial sample.
    """
    if total_scanned_kloc <= 0 or total_spend <= 0:
        return None, "none"
    rate = total_spend / total_scanned_kloc
    confidence = "medium" if total_scanned_kloc >= 100 else "low"
    return rate, confidence


def monitored_version_counts(versions: list[dict]) -> dict[str, int]:
    """Monitored-version count per parent Project uuid, from RepositoryVersion objects."""
    counts: dict[str, int] = {}
    for obj in versions:
        parent = (obj.get("meta") or {}).get("parent_uuid")
        if parent:
            counts[parent] = counts.get(parent, 0) + 1
    return counts


def ai_sast_scanned_projects(versions: list[dict]) -> set[str]:
    """Parent Project uuids that already have an AI-SAST-indexed or -scanned version.

    Reads RepositoryVersion.scan_object.aisast_status: a version qualifies if it was
    indexed (last_full_index_time / last_full_index_sha set) or has a completed scan
    (last_scan_state == AISAST_SCAN_STATE_SCAN_SUCCEEDED). Either means AI SAST credits
    were spent, which is exactly what makes the repo a valid cost-calibration sample.
    """
    scanned: set[str] = set()
    for obj in versions:
        parent = (obj.get("meta") or {}).get("parent_uuid")
        if not parent:
            continue
        status = (obj.get("scan_object") or {}).get("aisast_status") or {}
        if (
            status.get("last_full_index_time")
            or status.get("last_full_index_sha")
            or status.get("last_scan_state") == "AISAST_SCAN_STATE_SCAN_SUCCEEDED"
        ):
            scanned.add(parent)
    return scanned


def monitored_version_multiplier(monitored_versions: int, k: float = MONITORED_VERSION_K) -> float:
    """Cost multiplier for extra monitored branches: 1 + k*(n-1), floored at 1.0."""
    n = max(1, int(monitored_versions or 1))
    return 1.0 + k * (n - 1)


def size_bucket_cost(kloc: float) -> float:
    """Fixed per-repo cost estimate when no calibration exists."""
    for threshold, cost in SIZE_BUCKETS:
        if kloc < threshold:
            return cost
    return SIZE_BUCKET_LARGE_COST


def estimate_tier1_cost(
    kloc: float,
    rate: Optional[float],
    monitored_versions: int,
    k: float = MONITORED_VERSION_K,
) -> float:
    """Estimated first-window Tier-1 credit cost (the onboarding-baseline worst case).

    Uses the calibrated $/KLOC rate when available, else the size-bucket fallback,
    then scales by the monitored-version multiplier.
    """
    base = size_bucket_cost(kloc) if rate is None else kloc * rate
    return base * monitored_version_multiplier(monitored_versions, k)


def estimate_tier2_cost(finding_count: int, per_finding: float = PER_FINDING_TIER2_COST) -> float:
    """Heuristic Tier-2 (FP-triage) cost. NOT calibrated from observed spend (spec §5.4)."""
    return max(0, int(finding_count or 0)) * per_finding


def normalize_series(values: pd.Series) -> pd.Series:
    """Min-max normalize to 0..1. All-equal (incl. all-zero) series -> all zeros."""
    if values.empty:
        return values
    lo = float(values.min())
    hi = float(values.max())
    if hi <= lo:
        return pd.Series([0.0] * len(values), index=values.index)
    return (values - lo) / (hi - lo)


def value_score(components: dict[str, float], weights: dict[str, float] = DEFAULT_WEIGHTS) -> float:
    """Weighted blend of normalized value components (activity, findings, release)."""
    total_weight = sum(weights.values())
    if total_weight <= 0:
        return 0.0
    score = sum(components.get(name, 0.0) * w for name, w in weights.items())
    return score / total_weight


@dataclass
class AllocationParams:
    """Knobs for a single allocation run (all UI-tunable)."""

    budget: float
    safety_margin: float = SAFETY_MARGIN
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    gate_threshold: float = LANGUAGE_GATE_THRESHOLD
    monitored_version_k: float = MONITORED_VERSION_K
    cost_rate: Optional[float] = None  # calibrated $/KLOC, or None for size buckets


def allocate_tiers(repos: pd.DataFrame, params: AllocationParams) -> pd.DataFrame:
    """Assign a tier to every repo via greedy value-density packing under budget.

    Expected input columns (one row per project):
      project, languages (dict lang->bytes), monitored_versions (int),
      activity (float, raw), findings (int, target-class/high-sev count),
      release_signal (float, raw e.g. tag count).

    Output adds columns:
      supported_share, kloc, value, est_cost, vc_ratio, tier (1/2/3),
      rank (Tier-1 promotion order or NaN), rationale.
    """
    out_cols = [
        "supported_share", "kloc", "value", "est_cost", "vc_ratio", "tier", "rank", "rationale",
    ]
    if repos.empty:
        return repos.assign(**{c: pd.Series(dtype="float") for c in out_cols})

    df = repos.copy().reset_index(drop=True)

    df["supported_share"] = df["languages"].apply(supported_language_share)
    df["kloc"] = df["languages"].apply(lambda m: supported_kloc(m))
    df["eligible"] = df["supported_share"].apply(lambda s: passes_language_gate(s, params.gate_threshold))

    # Normalize value components across the eligible population.
    eligible_mask = df["eligible"]
    for raw, norm in (("activity", "n_activity"), ("findings", "n_findings"), ("release_signal", "n_release")):
        col = pd.to_numeric(df.get(raw, 0), errors="coerce").fillna(0.0)
        normed = pd.Series(0.0, index=df.index)
        if eligible_mask.any():
            normed.loc[eligible_mask] = normalize_series(col[eligible_mask])
        df[norm] = normed

    df["value"] = df.apply(
        lambda r: value_score(
            {"activity": r["n_activity"], "findings": r["n_findings"], "release": r["n_release"]},
            params.weights,
        ),
        axis=1,
    )
    df["est_cost"] = df.apply(
        lambda r: estimate_tier1_cost(r["kloc"], params.cost_rate, r["monitored_versions"], params.monitored_version_k),
        axis=1,
    )
    df["vc_ratio"] = df.apply(
        lambda r: (r["value"] / r["est_cost"]) if r["est_cost"] > 0 else 0.0, axis=1
    )

    df["tier"] = 3
    df["rank"] = pd.NA
    df["rationale"] = ""

    # Language-gated repos are Tier 3 regardless of value.
    df.loc[~df["eligible"], "rationale"] = df.loc[~df["eligible"], "supported_share"].apply(
        lambda s: f"Tier 3: only {s * 100:.0f}% supported-language code (gate {params.gate_threshold * 100:.0f}%)."
    )

    budget_cap = params.budget * (1.0 - params.safety_margin)
    committed = 0.0

    eligible = df[df["eligible"]].sort_values("vc_ratio", ascending=False)

    # Pass 1: promote to Tier 1 by value-density until the (margin-adjusted) budget is committed.
    rank = 0
    for idx in eligible.index:
        cost = df.at[idx, "est_cost"]
        if committed + cost <= budget_cap:
            rank += 1
            committed += cost
            df.at[idx, "tier"] = 1
            df.at[idx, "rank"] = rank
            df.at[idx, "rationale"] = (
                f"Tier 1: V/C rank #{rank}, est ${cost:.2f} first-window "
                f"(committed ${committed:.2f} / ${budget_cap:.2f} usable)."
            )

    # Pass 2: remaining eligible repos with findings get Tier 2 while budget remains.
    for idx in eligible.index:
        if df.at[idx, "tier"] == 1:
            continue
        findings = int(pd.to_numeric(df.at[idx, "findings"], errors="coerce") or 0)
        if findings <= 0:
            df.at[idx, "rationale"] = "Tier 3: eligible but no findings to triage."
            continue
        t2 = estimate_tier2_cost(findings)
        if committed + t2 <= budget_cap:
            committed += t2
            df.at[idx, "tier"] = 2
            df.at[idx, "rationale"] = f"Tier 2: rule-based + FP triage, est ${t2:.2f} (heuristic)."
        else:
            df.at[idx, "rationale"] = "Tier 3: budget exhausted before promotion."

    return df.drop(columns=["eligible", "n_activity", "n_findings", "n_release"])


def allocation_summary(allocated: pd.DataFrame, params: AllocationParams) -> dict[str, float]:
    """Estate roll-up: per-tier counts, projected spend, and headroom vs budget."""
    if allocated.empty:
        return {
            "tier1_count": 0, "tier2_count": 0, "tier3_count": 0,
            "projected_spend": 0.0, "budget": params.budget,
            "usable_budget": params.budget * (1 - params.safety_margin),
            "headroom": params.budget * (1 - params.safety_margin),
        }
    tier1 = allocated[allocated["tier"] == 1]
    tier2 = allocated[allocated["tier"] == 2]
    projected = float(tier1["est_cost"].sum()) + float(
        tier2["findings"].apply(lambda f: estimate_tier2_cost(int(f or 0))).sum()
    )
    usable = params.budget * (1 - params.safety_margin)
    return {
        "tier1_count": int(len(tier1)),
        "tier2_count": int(len(tier2)),
        "tier3_count": int((allocated["tier"] == 3).sum()),
        "projected_spend": projected,
        "budget": params.budget,
        "usable_budget": usable,
        "headroom": usable - projected,
    }
