#!/usr/bin/env python3
"""
AI Credit Usage Dashboard - Streamlit app.

Visualizes AI SAST / LLM-backed feature credit usage against the tenant's
quota: current usage vs. limit, burn rate, projected exhaustion, and a
per-model breakdown over selectable lookback windows.
"""

import subprocess
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import altair as alt
import pandas as pd
import streamlit as st

from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
    Table, TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from compute import (
    PRESETS,
    compute_fetch_days,
    is_non_standard_window,
    slice_window,
    windowed_usage,
    pct_used,
    threshold_state,
    burn_rate,
    projected_exhaustion_date,
    model_breakdown,
    daily_series,
    pick_day_locator_interval,
)


def run_endorctl(args: List[str], namespace: str, timeout: int = 120) -> Optional[Dict[str, Any]]:
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


def fetch_license(namespace: str) -> Optional[Dict[str, float]]:
    """Fetch the tenant's AI credit quota: {'days': int, 'max_credit': float}. None if unavailable."""
    response = run_endorctl(
        ["api", "list", "-r", "EndorLicense", "--field-mask", "spec.quota.ai_limit"],
        namespace,
    )
    if not response:
        return None
    objects = response.get("list", {}).get("objects", [])
    if not objects:
        return None
    ai_limit = objects[0].get("spec", {}).get("quota", {}).get("ai_limit", {})
    days = ai_limit.get("days")
    max_credit = ai_limit.get("max_credit")
    if days is None or max_credit is None:
        return None
    return {"days": int(days), "max_credit": float(max_credit)}


def fetch_usage(namespace: str, fetch_days: int) -> pd.DataFrame:
    """Fetch AICreditMetric rows for the trailing `fetch_days` days. Columns: accrued_date, llm, llm_cost."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=fetch_days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    response = run_endorctl(
        [
            "api", "list", "-r", "AICreditMetric",
            "--filter", f"spec.accrued_date >= {cutoff}",
            "--field-mask", "spec.llm_cost,spec.accrued_date,spec.llm",
            "--list-all",
        ],
        namespace,
        timeout=300,
    )

    columns = ["accrued_date", "llm", "llm_cost"]
    if not response:
        return pd.DataFrame(columns=columns)

    rows = []
    for obj in response.get("list", {}).get("objects", []):
        spec = obj.get("spec", {})
        rows.append({
            "accrued_date": spec.get("accrued_date"),
            "llm": spec.get("llm", "UNKNOWN"),
            "llm_cost": spec.get("llm_cost", 0.0),
        })

    if not rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows)
    df["accrued_date"] = pd.to_datetime(df["accrued_date"], utc=True, errors="coerce")
    return df


BRAND = {
    "green": "#00D26A",
    "dark": "#1A1A2E",
    "warn": "#fbc02d",
    "high": "#fb8c00",
    "critical": "#d32f2f",
    "text_primary": "#1A1A2E",
    "text_secondary": "#5A6577",
    "white": "#FFFFFF",
    "table_header_bg": "#1A1A2E",
    "table_header_text": "#FFFFFF",
    "table_row_alt": "#F8F9FA",
    "table_border": "#DEE2E6",
}


def _fig_to_rl_image(fig, width: float, height: float) -> RLImage:
    """Convert a matplotlib figure to a ReportLab Image."""
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return RLImage(buf, width=width, height=height)


def _build_trend_chart(usage_df: pd.DataFrame, window_days: int, page_width: float) -> RLImage:
    """Render the daily-cost bar chart for the PDF."""
    daily = daily_series(usage_df, window_days)

    fig, ax = plt.subplots(figsize=(page_width / 72, 2.8))
    fig.set_facecolor(BRAND["white"])
    ax.set_facecolor(BRAND["white"])

    if not daily.empty:
        ax.bar(daily["day"], daily["cost"], width=0.8, color=BRAND["green"], edgecolor="none")

    ax.set_ylabel("Daily cost ($)", fontsize=9, color=BRAND["text_secondary"])
    ax.grid(axis="y", linestyle="-", alpha=0.15, color="#AAAAAA")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#DDDDDD")
    ax.spines["bottom"].set_color("#DDDDDD")
    ax.tick_params(colors=BRAND["text_secondary"], labelsize=8)
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=pick_day_locator_interval(window_days)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8)
    fig.tight_layout()

    return _fig_to_rl_image(fig, page_width, 2.8 * 72)


def generate_pdf(namespace: str, license_info: Dict[str, float], usage_df: pd.DataFrame,
                  window_label: str, window_days: int) -> bytes:
    """Render a branded PDF summary: headline metrics, trend chart, model breakdown table."""
    buf = BytesIO()
    page_w, page_h = landscape(letter)
    margin = 0.6 * inch
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter),
                             leftMargin=margin, rightMargin=margin,
                             topMargin=margin, bottomMargin=margin)
    usable_width = page_w - 2 * margin

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Title2", parent=styles["Title"], fontSize=20,
                               textColor=HexColor(BRAND["dark"]), spaceAfter=4))
    styles.add(ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=10,
                               textColor=HexColor(BRAND["text_secondary"]), spaceAfter=12))
    styles.add(ParagraphStyle("SectionHeader", parent=styles["Heading2"], fontSize=13,
                               textColor=HexColor(BRAND["dark"]), spaceBefore=16, spaceAfter=8))

    elements = []
    elements.append(Paragraph("AI Credit Usage Report", styles["Title2"]))
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    elements.append(Paragraph(
        f"Namespace: {namespace}  |  Quota window: {license_info['days']} days  |  "
        f"Explorer window: {window_label}  |  Generated: {ts}",
        styles["Subtitle"],
    ))

    divider = Table([[""]], colWidths=[usable_width], rowHeights=[3])
    divider.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), HexColor(BRAND["green"]))]))
    elements.append(divider)
    elements.append(Spacer(1, 12))

    headline_usage = windowed_usage(usage_df, license_info["days"])
    fraction = pct_used(headline_usage, license_info["max_credit"])
    band = threshold_state(fraction)
    remaining = license_info["max_credit"] - headline_usage
    rate = burn_rate(usage_df)
    exhaustion = projected_exhaustion_date(remaining, rate)
    exhaustion_str = exhaustion.strftime("%Y-%m-%d") if exhaustion else "N/A (negligible burn)"

    summary_data = [
        ["% Quota Used", "Credits Used / Max", "Remaining", "Burn Rate ($/day)", "Projected Exhaustion"],
        [f"{fraction * 100:.1f}%", f"{headline_usage:.2f} / {license_info['max_credit']:.2f}",
         f"{remaining:.2f}", f"{rate:.2f}", exhaustion_str],
    ]
    col_w = usable_width / 5
    summary_table = Table(summary_data, colWidths=[col_w] * 5, rowHeights=[20, 32])
    summary_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor(BRAND["text_secondary"])),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 14),
        ("TEXTCOLOR", (0, 1), (-1, 1), HexColor(BRAND["text_primary"] if band == "ok" else BRAND[band])),
        ("BACKGROUND", (0, 0), (-1, -1), HexColor(BRAND["table_row_alt"])),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor(BRAND["table_border"])),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, HexColor(BRAND["table_border"])),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 12))

    if not usage_df.empty:
        elements.append(Paragraph(f"Trend ({window_label})", styles["SectionHeader"]))
        elements.append(_build_trend_chart(usage_df, window_days, usable_width))
        elements.append(Spacer(1, 8))

    breakdown = model_breakdown(usage_df, window_days)
    if not breakdown.empty:
        elements.append(Paragraph("Model Breakdown", styles["SectionHeader"]))
        bd_rows = [["Model", "Cost ($)", "% of Window"]]
        for _, row in breakdown.iterrows():
            bd_rows.append([row["llm"], f"{row['cost']:.2f}", f"{row['pct_of_window'] * 100:.1f}%"])
        bd_table = Table(bd_rows, colWidths=[usable_width * 0.5, usable_width * 0.25, usable_width * 0.25],
                          repeatRows=1)
        bd_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor(BRAND["table_header_bg"])),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor(BRAND["table_header_text"])),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor(BRAND["table_border"])),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor(BRAND["white"]), HexColor(BRAND["table_row_alt"])]),
        ]))
        elements.append(bd_table)

    doc.build(elements)
    return buf.getvalue()


THRESHOLD_LABELS = {
    "ok": "\U0001F7E2 OK (<50%)",
    "warn": "\U0001F7E1 Warning (50-80%)",
    "high": "\U0001F7E0 High (80-95%)",
    "critical": "\U0001F534 Critical (95%+)",
}


def main():
    st.set_page_config(
        page_title="AI Credit Usage Dashboard",
        page_icon="\U0001F9EE",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    if "usage_df" not in st.session_state:
        st.session_state.usage_df = None
        st.session_state.license_info = None
        st.session_state.namespace = None

    st.title("AI Credit Usage Dashboard")
    st.markdown(
        "Visualize AI SAST / LLM-backed feature credit usage against your tenant's quota: "
        "current usage, burn rate, projected exhaustion, and a per-model breakdown."
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
        generate = st.button("Generate/Refresh Report", type="primary", use_container_width=True)

    if generate:
        if not namespace:
            st.error("Please enter a namespace.")
            st.stop()

        with st.spinner("Fetching license quota..."):
            license_info = fetch_license(namespace)

        if not license_info:
            st.error("Could not read AI credit quota (EndorLicense.spec.quota.ai_limit) for this namespace.")
            st.stop()

        fetch_days = compute_fetch_days(license_info["days"])

        with st.spinner(f"Fetching usage (last {fetch_days} days)..."):
            usage_df = fetch_usage(namespace, fetch_days)

        st.session_state.usage_df = usage_df
        st.session_state.license_info = license_info
        st.session_state.namespace = namespace
        st.rerun()

    if st.session_state.license_info is None:
        st.info("Configure the namespace in the sidebar and click **Generate/Refresh Report**.")
        st.stop()

    license_info = st.session_state.license_info
    usage_df = st.session_state.usage_df
    namespace = st.session_state.namespace

    if is_non_standard_window(license_info["days"]):
        st.warning(
            f"Non-standard quota window detected: `days={license_info['days']}`. "
            f"This dashboard fetched only the last {compute_fetch_days(license_info['days'])} days of usage, "
            "so the headline number below does not reflect the full rolling window. "
            "Verify this configuration against the contract (2% SKU / 30 days)."
        )

    st.markdown("## Quota Summary")

    headline_usage = windowed_usage(usage_df, license_info["days"])
    fraction = pct_used(headline_usage, license_info["max_credit"])
    band = threshold_state(fraction)
    remaining = license_info["max_credit"] - headline_usage
    rate = burn_rate(usage_df)
    exhaustion = projected_exhaustion_date(remaining, rate)
    exhaustion_str = exhaustion.strftime("%Y-%m-%d") if exhaustion else "N/A (negligible burn)"

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("% Quota Used", f"{fraction * 100:.1f}%")
    col2.metric("Credits Used / Max", f"{headline_usage:.2f} / {license_info['max_credit']:.2f}")
    col3.metric("Remaining", f"{remaining:.2f}")
    col4.metric("Burn Rate ($/day)", f"{rate:.2f}")
    col5.metric("Projected Exhaustion", exhaustion_str)

    st.markdown(f"**Threshold band:** {THRESHOLD_LABELS[band]}")
    st.caption(
        f"Namespace: `{namespace}`  |  Quota window: {license_info['days']} days  |  "
        f"Max credit: {license_info['max_credit']:.2f}"
    )

    st.markdown("## Explorer")

    window_label = st.selectbox("Lookback window", options=list(PRESETS.keys()), index=1)
    window_days = PRESETS[window_label]

    windowed_df = slice_window(usage_df, window_days)

    if windowed_df.empty:
        st.info(f"No usage data in the selected window ({window_label}).")
        return

    st.markdown("### Trend")

    daily_totals = daily_series(usage_df, window_days).rename(columns={"cost": "llm_cost"})
    daily_totals["cumulative"] = daily_totals["llm_cost"].cumsum()

    bar = alt.Chart(daily_totals).mark_bar(color="#00D26A").encode(
        x=alt.X("day:T", title="Date"),
        y=alt.Y("llm_cost:Q", title="Daily cost ($)"),
        tooltip=["day:T", "llm_cost:Q"],
    )

    line = alt.Chart(daily_totals).mark_line(color="#1A1A2E", strokeWidth=2).encode(
        x="day:T",
        y=alt.Y("cumulative:Q", title="Cumulative cost ($)"),
        tooltip=["day:T", "cumulative:Q"],
    )

    quota_line = alt.Chart(pd.DataFrame({"y": [license_info["max_credit"]]})).mark_rule(
        color="#d32f2f", strokeDash=[4, 4]
    ).encode(y="y:Q")

    st.altair_chart(
        alt.layer(bar, line + quota_line).resolve_scale(y="independent"),
        use_container_width=True,
    )
    st.caption(
        "Bars: daily cost (left axis). Line: cumulative cost in window vs. max_credit "
        "reference (right axis, dashed red)."
    )

    st.markdown("### Model Breakdown")
    breakdown = model_breakdown(usage_df, window_days)
    breakdown_display = breakdown.copy()
    breakdown_display["pct_of_window"] = (breakdown_display["pct_of_window"] * 100).round(1)
    st.dataframe(
        breakdown_display,
        use_container_width=True,
        column_config={
            "llm": st.column_config.TextColumn("Model"),
            "cost": st.column_config.NumberColumn("Cost ($)", format="%.2f"),
            "pct_of_window": st.column_config.NumberColumn("% of Window", format="%.1f%%"),
        },
    )

    st.markdown("### Raw Data")
    st.dataframe(
        windowed_df.sort_values("accrued_date", ascending=False),
        use_container_width=True,
        height=400,
        column_config={
            "accrued_date": st.column_config.DatetimeColumn("Date", format="YYYY-MM-DD"),
            "llm": st.column_config.TextColumn("Model"),
            "llm_cost": st.column_config.NumberColumn("Cost ($)", format="%.4f"),
        },
    )

    st.markdown("## Export")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    ecol1, ecol2 = st.columns(2)

    with ecol1:
        st.download_button(
            label="Download CSV",
            data=windowed_df.to_csv(index=False),
            file_name=f"ai_credit_usage_{namespace}_{ts}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with ecol2:
        pdf_data = generate_pdf(namespace, license_info, usage_df, window_label, window_days)
        st.download_button(
            label="Download PDF",
            data=pdf_data,
            file_name=f"ai_credit_usage_{namespace}_{ts}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
