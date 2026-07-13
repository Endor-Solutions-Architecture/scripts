#!/usr/bin/env python3
"""
AI SAST Tier Recommender - Streamlit app.

Given a namespace, recommends a tier (1/2/3) per repository that maximizes
security value while fitting the tenant's AI credit budget, with an
explainable rationale per repo. Advisory only — never applies scan profiles
or changes quota.

Mirrors the ai_credit_dashboard pattern: pure logic in compute.py, all I/O
here, one endorctl pull per "Generate" cached in session_state, then
re-allocation happens client-side as the sidebar knobs change.
"""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

import compute
from compute import AllocationParams


# --- endorctl I/O (same wrapper as the spend dashboard) ---

def run_endorctl(args: List[str], namespace: str, timeout: int = 300) -> Optional[Dict[str, Any]]:
    """Execute an endorctl command and return parsed JSON."""
    cmd = ["endorctl", "-n", namespace] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
        if result.stdout.strip():
            return json.loads(result.stdout)
        return None
    except subprocess.CalledProcessError as e:
        st.error(f"endorctl error: {e.stderr}")
        return None
    except subprocess.TimeoutExpired:
        st.error(f"Command timed out: {' '.join(cmd)}")
        return None
    except json.JSONDecodeError as e:
        st.error(f"JSON parse error: {e}")
        return None


def _objects(response: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not response:
        return []
    return response.get("list", {}).get("objects", [])


def fetch_license(namespace: str) -> Optional[Dict[str, float]]:
    """Fetch the tenant's AI credit quota: {'days': int, 'max_credit': float}. None if unavailable."""
    response = run_endorctl(
        ["api", "list", "-r", "EndorLicense", "--field-mask", "spec.quota.ai_limit"], namespace
    )
    objects = _objects(response)
    if not objects:
        return None
    ai_limit = objects[0].get("spec", {}).get("quota", {}).get("ai_limit", {})
    days = ai_limit.get("days")
    max_credit = ai_limit.get("max_credit")
    if days is None or max_credit is None:
        return None
    return {"days": int(days), "max_credit": float(max_credit)}


def fetch_total_ai_spend(namespace: str, days: int = 180) -> float:
    """Sum of observed AICreditMetric llm_cost over the trailing window (calibration numerator)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    response = run_endorctl(
        [
            "api", "list", "-r", "AICreditMetric",
            "--filter", f"spec.accrued_date >= {cutoff}",
            "--field-mask", "spec.llm_cost", "--list-all",
        ],
        namespace,
    )
    return sum(float(o.get("spec", {}).get("llm_cost", 0.0) or 0.0) for o in _objects(response))


def _parse_languages(languages_field: Any) -> Dict[str, float]:
    """Best-effort extraction of a {language_name: bytes} map from Repository.spec.languages.

    The field wraps a raw ingested object whose exact shape varies by SCM; we
    defensively pull out the first nested {str: number} mapping we find.
    """
    def find_map(node: Any) -> Dict[str, float]:
        if isinstance(node, dict):
            numeric = {k: float(v) for k, v in node.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
            if numeric:
                return numeric
            for v in node.values():
                found = find_map(v)
                if found:
                    return found
        return {}

    return find_map(languages_field)


def fetch_repositories(namespace: str) -> pd.DataFrame:
    """One row per repository: uuid, project (name), languages (dict), release_signal (tag count)."""
    response = run_endorctl(
        [
            "api", "list", "-r", "Repository",
            "--field-mask", "meta.name,spec.languages,spec.tags,spec.default_branch",
            "--list-all",
        ],
        namespace,
    )
    rows = []
    for obj in _objects(response):
        spec = obj.get("spec", {})
        rows.append({
            "uuid": obj.get("uuid"),
            "project": obj.get("meta", {}).get("name", "unknown"),
            "languages": _parse_languages(spec.get("languages")),
            "release_signal": float(len(spec.get("tags") or [])),
        })
    return pd.DataFrame(rows, columns=["uuid", "project", "languages", "release_signal"])


def fetch_monitored_version_counts(namespace: str) -> Dict[str, int]:
    """Count of monitored RepositoryVersions per repository uuid (meta.parent_uuid)."""
    response = run_endorctl(
        ["api", "list", "-r", "RepositoryVersion", "--field-mask", "meta.parent_uuid", "--list-all"],
        namespace,
    )
    counts: Dict[str, int] = {}
    for obj in _objects(response):
        parent = obj.get("meta", {}).get("parent_uuid")
        if parent:
            counts[parent] = counts.get(parent, 0) + 1
    return counts


def fetch_activity(namespace: str) -> Dict[str, float]:
    """Best-effort recent commit activity per repository uuid, from Metric TimeTracker slots.

    Returns {} if metrics can't be read; the activity component then scores 0 (flagged in the UI).
    """
    try:
        response = run_endorctl(
            ["api", "list", "-r", "Metric", "--field-mask", "meta.parent_uuid,spec.metric_values", "--list-all"],
            namespace,
        )
    except Exception:
        return {}

    activity: Dict[str, float] = {}
    for obj in _objects(response):
        parent = obj.get("meta", {}).get("parent_uuid")
        if not parent:
            continue
        tracker = _find_time_tracker(obj.get("spec", {}))
        if tracker is None:
            continue
        slots = tracker.get("monthly_activity") or tracker.get("daily_activity") or []
        recent = sum(float(s.get("count", 0) or 0) for s in slots[-3:])
        if recent:
            activity[parent] = activity.get(parent, 0.0) + recent
    return activity


def _find_time_tracker(node: Any) -> Optional[Dict[str, Any]]:
    """Locate a TimeTracker-shaped dict (has *_activity slot lists) anywhere in a metric spec."""
    if isinstance(node, dict):
        if any(k in node for k in ("daily_activity", "monthly_activity", "yearly_activity")):
            return node
        for v in node.values():
            found = _find_time_tracker(v)
            if found:
                return found
    elif isinstance(node, list):
        for v in node:
            found = _find_time_tracker(v)
            if found:
                return found
    return None


def fetch_finding_counts(namespace: str) -> Dict[str, int]:
    """Best-effort count of high-severity findings per repository uuid.

    Findings taxonomy varies; this is intentionally coarse and defaults to
    empty (so the findings component scores 0) rather than failing the run.
    """
    try:
        response = run_endorctl(
            [
                "api", "list", "-r", "Finding",
                "--filter", "spec.level == FINDING_LEVEL_CRITICAL or spec.level == FINDING_LEVEL_HIGH",
                "--field-mask", "meta.parent_uuid", "--list-all",
            ],
            namespace,
        )
    except Exception:
        return {}

    counts: Dict[str, int] = {}
    for obj in _objects(response):
        parent = obj.get("meta", {}).get("parent_uuid")
        if parent:
            counts[parent] = counts.get(parent, 0) + 1
    return counts


def assemble_repos(namespace: str) -> pd.DataFrame:
    """Fetch and join all per-repo signals into the allocator's input frame."""
    repos = fetch_repositories(namespace)
    if repos.empty:
        return repos.assign(monitored_versions=pd.Series(dtype="int"),
                            activity=pd.Series(dtype="float"), findings=pd.Series(dtype="int"))
    mv = fetch_monitored_version_counts(namespace)
    activity = fetch_activity(namespace)
    findings = fetch_finding_counts(namespace)

    repos["monitored_versions"] = repos["uuid"].map(lambda u: mv.get(u, 1)).fillna(1).astype(int)
    repos["activity"] = repos["uuid"].map(lambda u: activity.get(u, 0.0)).fillna(0.0)
    repos["findings"] = repos["uuid"].map(lambda u: findings.get(u, 0)).fillna(0).astype(int)
    return repos


# --- Presentation ---

BRAND = {
    "green": "#00D26A", "dark": "#1A1A2E", "tier1": "#00D26A", "tier2": "#fbc02d",
    "tier3": "#5A6577", "text_primary": "#1A1A2E", "text_secondary": "#5A6577",
    "white": "#FFFFFF", "table_header_bg": "#1A1A2E", "table_header_text": "#FFFFFF",
    "table_row_alt": "#F8F9FA", "table_border": "#DEE2E6",
}

TIER_LABELS = {1: "Tier 1 (AI SAST agent)", 2: "Tier 2 (rules + FP triage)", 3: "Tier 3 (rules only)"}


def _display_frame(allocated: pd.DataFrame) -> pd.DataFrame:
    """Human-readable columns for the recommendation table and exports."""
    cols = ["project", "tier", "rank", "value", "est_cost", "vc_ratio",
            "supported_share", "monitored_versions", "findings", "rationale"]
    df = allocated[[c for c in cols if c in allocated.columns]].copy()
    df = df.sort_values(["tier", "rank", "value"], ascending=[True, True, False], na_position="last")
    df["project"] = df["project"].map(compute.short_repo_name)
    df["tier"] = df["tier"].map(lambda t: TIER_LABELS.get(int(t), str(t)))
    df["supported_share"] = (df["supported_share"] * 100).round(0)
    df["value"] = df["value"].round(3)
    df["est_cost"] = df["est_cost"].round(2)
    df["vc_ratio"] = df["vc_ratio"].round(4)
    return df.rename(columns={
        "project": "Repository", "tier": "Tier", "rank": "T1 Rank", "value": "Value",
        "est_cost": "Est. Cost ($)", "vc_ratio": "Value/Cost", "supported_share": "Supported %",
        "monitored_versions": "Monitored Vers.", "findings": "High-sev Findings", "rationale": "Rationale",
    })


def _fig_to_rl_image(fig, width: float, height: float) -> RLImage:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return RLImage(buf, width=width, height=height)


def _tier_distribution_chart(summary: Dict[str, float], page_width: float) -> RLImage:
    fig, ax = plt.subplots(figsize=(page_width / 72, 2.2))
    fig.set_facecolor(BRAND["white"])
    ax.set_facecolor(BRAND["white"])
    tiers = ["Tier 1", "Tier 2", "Tier 3"]
    counts = [summary["tier1_count"], summary["tier2_count"], summary["tier3_count"]]
    ax.bar(tiers, counts, color=[BRAND["tier1"], BRAND["tier2"], BRAND["tier3"]], edgecolor="none")
    ax.set_ylabel("Repositories", fontsize=9, color=BRAND["text_secondary"])
    ax.grid(axis="y", linestyle="-", alpha=0.15, color="#AAAAAA")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(colors=BRAND["text_secondary"], labelsize=9)
    fig.tight_layout()
    return _fig_to_rl_image(fig, page_width, 2.2 * 72)


def generate_pdf(namespace: str, summary: Dict[str, float], display_df: pd.DataFrame,
                  confidence: str, params: AllocationParams) -> bytes:
    buf = BytesIO()
    page_w, _ = landscape(letter)
    margin = 0.6 * inch
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=margin,
                            rightMargin=margin, topMargin=margin, bottomMargin=margin)
    usable_width = page_w - 2 * margin

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Title2", parent=styles["Title"], fontSize=20, textColor=HexColor(BRAND["dark"]), spaceAfter=4))
    styles.add(ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=10, textColor=HexColor(BRAND["text_secondary"]), spaceAfter=12))
    styles.add(ParagraphStyle("SectionHeader", parent=styles["Heading2"], fontSize=13, textColor=HexColor(BRAND["dark"]), spaceBefore=14, spaceAfter=8))

    elements = [Paragraph("AI SAST Tier Recommendations", styles["Title2"])]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    elements.append(Paragraph(
        f"Namespace: {namespace}  |  Budget: ${params.budget:.2f}  |  Safety margin: {params.safety_margin * 100:.0f}%  |  "
        f"Cost confidence: {confidence}  |  Generated: {ts}",
        styles["Subtitle"],
    ))
    divider = Table([[""]], colWidths=[usable_width], rowHeights=[3])
    divider.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), HexColor(BRAND["green"]))]))
    elements.append(divider)
    elements.append(Spacer(1, 12))

    summary_data = [
        ["Tier 1", "Tier 2", "Tier 3", "Projected Spend", "Usable Budget", "Headroom"],
        [str(summary["tier1_count"]), str(summary["tier2_count"]), str(summary["tier3_count"]),
         f"${summary['projected_spend']:.2f}", f"${summary['usable_budget']:.2f}", f"${summary['headroom']:.2f}"],
    ]
    col_w = usable_width / 6
    summary_table = Table(summary_data, colWidths=[col_w] * 6, rowHeights=[20, 30])
    summary_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, 0), 9), ("TEXTCOLOR", (0, 0), (-1, 0), HexColor(BRAND["text_secondary"])),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"), ("FONTSIZE", (0, 1), (-1, 1), 13),
        ("BACKGROUND", (0, 0), (-1, -1), HexColor(BRAND["table_row_alt"])),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor(BRAND["table_border"])),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Tier Distribution", styles["SectionHeader"]))
    elements.append(_tier_distribution_chart(summary, usable_width))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("Recommendations", styles["SectionHeader"]))
    show = display_df.drop(columns=["Rationale"], errors="ignore")
    table_rows = [list(show.columns)] + show.astype(str).values.tolist()
    n = len(show.columns)
    rec_table = Table(table_rows, colWidths=[usable_width / n] * n, repeatRows=1)
    rec_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor(BRAND["table_header_bg"])),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor(BRAND["table_header_text"])),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7), ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.5, HexColor(BRAND["table_border"])),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor(BRAND["white"]), HexColor(BRAND["table_row_alt"])]),
    ]))
    elements.append(rec_table)

    doc.build(elements)
    return buf.getvalue()


def main():
    st.set_page_config(page_title="AI SAST Tier Recommender", page_icon="\U0001F6E1",
                       layout="wide", initial_sidebar_state="expanded")

    for key in ("repos_df", "license_info", "namespace", "total_spend"):
        st.session_state.setdefault(key, None)

    st.title("AI SAST Tier Recommender")
    st.markdown(
        "Recommends a tier per repository that maximizes security value while fitting the tenant's "
        "AI credit budget. **Advisory only** — it never applies scan profiles or changes quota."
    )
    st.markdown("---")

    with st.sidebar:
        st.header("Configuration")
        try:
            subprocess.run(["endorctl", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            st.success("endorctl available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            st.error("endorctl not found in PATH")
            st.stop()

        namespace = st.text_input("Namespace", value="", help="Root tenant namespace to query")
        generate = st.button("Generate/Refresh", type="primary", use_container_width=True)

    if generate:
        if not namespace:
            st.error("Please enter a namespace.")
            st.stop()
        with st.spinner("Fetching license quota..."):
            license_info = fetch_license(namespace)
        if not license_info:
            st.error("Could not read AI credit quota (EndorLicense.spec.quota.ai_limit) for this namespace.")
            st.stop()
        with st.spinner("Fetching repositories and signals (this can take a minute)..."):
            repos_df = assemble_repos(namespace)
            total_spend = fetch_total_ai_spend(namespace)
        st.session_state.repos_df = repos_df
        st.session_state.license_info = license_info
        st.session_state.namespace = namespace
        st.session_state.total_spend = total_spend
        st.rerun()

    if st.session_state.license_info is None:
        st.info("Configure the namespace in the sidebar and click **Generate/Refresh**.")
        st.stop()

    license_info = st.session_state.license_info
    repos_df = st.session_state.repos_df
    namespace = st.session_state.namespace
    total_spend = st.session_state.total_spend or 0.0

    if repos_df is None or repos_df.empty:
        st.warning("No repositories found in this namespace.")
        st.stop()

    if license_info["days"] == 0 or license_info["max_credit"] <= 0:
        st.error(
            "AI credit quota is not configured (`days == 0` or `max_credit == 0`). "
            "Budget-aware allocation needs a real quota — set it via a service request first. "
            "Note: with no quota configured, no usage is ever metered either."
        )
        st.stop()

    # --- Tunable knobs (re-allocation is client-side; no re-fetch) ---
    with st.sidebar:
        st.markdown("---")
        st.subheader("Allocation knobs")
        budget = st.number_input(
            "Budget (credits = $)", min_value=0.0, value=float(license_info["max_credit"]), step=10.0,
            help="Total AI credit pool to allocate against (1 credit = US$1 of LLM spend). Defaults to the "
                 "license's max_credit; override it for what-if planning.",
        )
        safety_margin = st.slider(
            "Safety margin", 0.0, 0.5, compute.SAFETY_MARGIN, 0.05,
            help="Fraction of the budget held back as headroom. Tier 1 promotion stops once committed cost "
                 "reaches budget × (1 − margin), so estimation error doesn't blow the pool.",
        )
        gate_threshold = st.slider(
            "Language gate (supported byte share)", 0.0, 1.0, compute.LANGUAGE_GATE_THRESHOLD, 0.05,
            help="Minimum share of a repo's code (by bytes) written in AI-SAST-supported languages to be "
                 "eligible for Tier 1/2. Below this a repo goes straight to Tier 3 — AI SAST can't help it.",
        )
        mv_k = st.slider(
            "Monitored-version cost multiplier (k)", 0.0, 1.0, compute.MONITORED_VERSION_K, 0.05,
            help="How much each extra monitored branch adds to a repo's estimated cost: "
                 "multiplier = 1 + k × (monitored versions − 1). Release branches are scanned too, so more "
                 "monitored versions cost more.",
        )
        st.caption("Value weights (auto-normalized)")
        w_activity = st.slider(
            "Activity", 0.0, 1.0, compute.DEFAULT_WEIGHTS["activity"], 0.05,
            help="Weight of commit activity (from Metric history) in the value score. Active repos rank higher. "
                 "Weights are normalized, so only their ratios matter.",
        )
        w_findings = st.slider(
            "Findings", 0.0, 1.0, compute.DEFAULT_WEIGHTS["findings"], 0.05,
            help="Weight of high-severity finding density in the value score — where AI SAST's exploitability "
                 "reasoning pays off most. Weights are normalized, so only their ratios matter.",
        )
        w_release = st.slider(
            "Release/prod", 0.0, 1.0, compute.DEFAULT_WEIGHTS["release"], 0.05,
            help="Weight of the production signal (release tags + monitored-version count) in the value score. "
                 "Weights are normalized, so only their ratios matter.",
        )
        st.markdown("---")
        st.subheader("Cost calibration")
        st.caption(f"Observed AI spend (trailing 180d): ${total_spend:.2f}")
        scanned_repos = st.multiselect(
            "Calibrate cost from already-scanned repos",
            options=sorted(repos_df["project"].tolist()),
            default=[],
            format_func=compute.short_repo_name,
            help=(
                "Pick the repos you've already AI-SAST baselined. The tool sums their "
                "supported-language size (KLOC) and divides your observed AI spend by it to get a "
                "blended **$/KLOC** rate.\n\n"
                "That rate sets the **Est. Cost** for every repo, which drives **Projected Spend**, "
                "**Headroom**, and which repos get promoted to Tier 1 (allocation is budget-aware).\n\n"
                "Because AICreditMetric spend isn't attributable per repo, it's one tenant-wide rate — "
                "planning-grade, not exact. Select nothing to fall back to coarse size buckets."
            ),
        )
        scanned_langs = repos_df[repos_df["project"].isin(scanned_repos)]["languages"].tolist()
        scanned_kloc = compute.total_supported_kloc(scanned_langs)
        if scanned_repos:
            st.caption(f"Selected: {len(scanned_repos)} repos ≈ {scanned_kloc:,.0f} KLOC supported-language code")

    rate, confidence = compute.calibrate_cost_per_kloc(total_spend, scanned_kloc)

    params = AllocationParams(
        budget=budget, safety_margin=safety_margin,
        weights={"activity": w_activity, "findings": w_findings, "release": w_release},
        gate_threshold=gate_threshold, monitored_version_k=mv_k, cost_rate=rate,
    )

    allocated = compute.allocate_tiers(repos_df, params)
    summary = compute.allocation_summary(allocated, params)

    # --- Summary ---
    st.markdown("## Estate Summary")
    if confidence == "none":
        st.warning(
            "**Cost is uncalibrated** — no scanned-KLOC entered, so estimates use coarse size buckets. "
            "Enter KLOC already scanned in the sidebar (and rely on the safety margin) for a real fit."
        )
    else:
        st.info(f"Cost calibration: **{confidence}** confidence (${rate:.4f}/KLOC blended, tenant-wide — not per-feature or per-repo).")

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Tier 1", summary["tier1_count"])
    c2.metric("Tier 2", summary["tier2_count"])
    c3.metric("Tier 3", summary["tier3_count"])
    c4.metric("Projected Spend", f"${summary['projected_spend']:.2f}")
    c5.metric("Usable Budget", f"${summary['usable_budget']:.2f}")
    c6.metric("Headroom", f"${summary['headroom']:.2f}")

    if summary["headroom"] < 0:
        st.error("Projected spend exceeds the usable budget — tighten the gate, lower weights, or raise the budget.")

    st.markdown("## Recommendations")
    tier_filter = st.selectbox(
        "Filter by tier",
        options=["All tiers", "Tier 1 (AI SAST agent)", "Tier 2 (rules + FP triage)", "Tier 3 (rules only)"],
        help="Narrow the table (and its CSV/PDF export) to one tier. The estate summary above always reflects "
             "all repositories.",
    )
    if tier_filter == "All tiers":
        filtered = allocated
    else:
        tier_num = {v: k for k, v in TIER_LABELS.items()}[tier_filter]
        filtered = allocated[allocated["tier"] == tier_num]

    display_df = _display_frame(filtered)
    st.caption(f"Showing {len(display_df)} of {len(allocated)} repositories.")
    st.dataframe(display_df, use_container_width=True, height=460)

    st.caption(
        "Tier 1 = AI SAST agent (highest cost, exploitability-aware). "
        "Tier 2 = rule-based SAST + AI FP triage. Tier 3 = rule-based rules only (free of the pool). "
        "Recommendations are advisory."
    )

    # --- Export ---
    st.markdown("## Export")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    ecol1, ecol2 = st.columns(2)
    with ecol1:
        st.download_button("Download CSV", data=display_df.to_csv(index=False),
                           file_name=f"ai_sast_tiers_{namespace}_{ts}.csv", mime="text/csv",
                           use_container_width=True)
    with ecol2:
        pdf_data = generate_pdf(namespace, summary, display_df, confidence, params)
        st.download_button("Download PDF", data=pdf_data,
                           file_name=f"ai_sast_tiers_{namespace}_{ts}.pdf", mime="application/pdf",
                           use_container_width=True)


if __name__ == "__main__":
    main()
