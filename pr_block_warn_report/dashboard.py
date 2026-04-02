#!/usr/bin/env python3
"""
PR Block/Warn Report - Streamlit Dashboard

Interactive dashboard for exploring PR scans that triggered action policy
enforcement (block or warn). Provides filters, timeline charts, and CSV export.
"""

import subprocess
import json
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

import streamlit as st
import pandas as pd
import altair as alt


UI_BASE = "https://app.endorlabs.com"


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


def fetch_enforced_scan_results(namespace: str, days: int) -> List[Dict[str, Any]]:
    """Fetch ScanResults that have blocking or warning findings."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    filter_expr = (
        "(spec.blocking_findings exists or spec.warning_findings exists)"
        ' and context.type == "CONTEXT_TYPE_CI_RUN"'
        f' and meta.create_time > date("{cutoff}")'
    )

    response = run_endorctl(
        [
            "api", "list", "-r", "ScanResult",
            "--filter", filter_expr,
            "--field-mask", (
                "uuid,"
                "meta.create_time,"
                "meta.parent_uuid,"
                "meta.tags,"
                "tenant_meta.namespace,"
                "context.tags,"
                "spec.status,"
                "spec.blocking_findings,"
                "spec.warning_findings"
            ),
            "--sort-path", "meta.create_time",
            "--sort-order", "descending",
            "--list-all",
            "--traverse",
            "-t", "300s",
        ],
        namespace,
        timeout=360,
    )

    if not response:
        return []
    return response.get("list", {}).get("objects", [])


def extract_pr_number(scan_result: Dict[str, Any]) -> Optional[str]:
    """Extract PR number from context.tags or meta.tags (e.g. 'pr=1')."""
    for tag_source in [scan_result.get("context", {}).get("tags", []),
                       scan_result.get("meta", {}).get("tags", [])]:
        for tag in tag_source:
            if tag.startswith("pr="):
                return tag.split("=", 1)[1]
    return None


def resolve_project_info(namespace: str, project_uuids: List[str]) -> Dict[str, Dict[str, str]]:
    """Resolve project UUIDs to full_name and http_clone_url."""
    if not project_uuids:
        return {}

    uuid_list = "', '".join(project_uuids)
    response = run_endorctl(
        [
            "api", "list", "-r", "Project",
            "--filter", f"uuid in ['{uuid_list}']",
            "--field-mask", "uuid,tenant_meta.namespace,spec.git.full_name,spec.git.http_clone_url",
            "--list-all",
            "--traverse",
        ],
        namespace,
        timeout=120,
    )

    if not response:
        return {}

    projects = {}
    for obj in response.get("list", {}).get("objects", []):
        git = obj.get("spec", {}).get("git", {})
        clone_url = git.get("http_clone_url", "")
        base_url = clone_url.rstrip("/").removesuffix(".git") if clone_url else ""
        projects[obj.get("uuid", "")] = {
            "full_name": git.get("full_name", "Unknown"),
            "base_url": base_url,
            "namespace": obj.get("tenant_meta", {}).get("namespace", ""),
        }

    return projects


def build_pr_url(base_url: str, pr_number: Optional[str]) -> str:
    """Construct PR URL from project base URL and PR number."""
    if not base_url or not pr_number:
        return "N/A"
    return f"{base_url}/pull/{pr_number}"


def run_analysis(namespace: str, days: int) -> pd.DataFrame:
    """Fetch data and build the report DataFrame."""
    # Step 1: Get ScanResults with block/warn (small, targeted query)
    scan_results = fetch_enforced_scan_results(namespace, days)

    if not scan_results:
        st.warning("No ScanResults with block/warn findings found.")
        return pd.DataFrame()

    st.info(f"Found {len(scan_results)} ScanResults with block/warn findings.")

    # Step 2: Resolve project info in bulk
    project_uuids = list(set(
        sr.get("meta", {}).get("parent_uuid", "")
        for sr in scan_results
        if sr.get("meta", {}).get("parent_uuid")
    ))
    project_info = resolve_project_info(namespace, project_uuids)

    # Step 3: Build rows
    rows = []
    for sr in scan_results:
        sr_uuid = sr.get("uuid", "")
        meta = sr.get("meta", {})
        spec = sr.get("spec", {})
        project_uuid = meta.get("parent_uuid", "")
        proj = project_info.get(project_uuid, {"full_name": "Unknown", "base_url": "", "namespace": ""})

        # Use the project's namespace for URLs (correct for child namespaces)
        ns = proj["namespace"] or sr.get("tenant_meta", {}).get("namespace", namespace)

        blocking = spec.get("blocking_findings", [])
        warning = spec.get("warning_findings", [])
        outcome = "block" if blocking else "warn"

        pr_number = extract_pr_number(sr)

        rows.append({
            "date": meta.get("create_time", ""),
            "project_name": proj["full_name"],
            "project_url": f"{UI_BASE}/t/{ns}/projects/{project_uuid}",
            "pr_url": build_pr_url(proj["base_url"], pr_number),
            "scan_result_url": f"{UI_BASE}/t/{ns}/scan-history/{sr_uuid}",
            "outcome": outcome,
            "blocker_findings": len(blocking),
            "warning_findings": len(warning),
            "pr_check_conclusion": spec.get("status", ""),
        })

    if not rows:
        st.warning("No PR scans with block or warn findings in this time range.")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date", ascending=False).reset_index(drop=True)
    return df


def main():
    st.set_page_config(
        page_title="PR Block/Warn Report",
        page_icon="🔒",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Session state init
    if "df" not in st.session_state:
        st.session_state.df = None

    st.title("PR Block/Warn Report")
    st.markdown("Explore PR scans that triggered action policy enforcement (block or warn).")
    st.markdown("---")

    # --- Sidebar ---
    with st.sidebar:
        st.header("Configuration")

        try:
            subprocess.run(["endorctl", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            st.success("endorctl available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            st.error("endorctl not found in PATH")
            st.stop()

        namespace = st.text_input("Namespace", value="", help="Tenant namespace to query")

        lookback_options = {
            1: "Last 1 day",
            2: "Last 2 days",
            3: "Last 3 days",
            5: "Last 5 days",
            7: "Last 1 week",
            14: "Last 2 weeks",
            21: "Last 3 weeks (max retention)",
        }
        days = st.selectbox(
            "Lookback period",
            options=list(lookback_options.keys()),
            index=len(lookback_options) - 1,
            format_func=lambda d: lookback_options[d],
        )

        generate = st.button("Generate Report", type="primary", use_container_width=True)

    # --- Run analysis ---
    if generate:
        if not namespace:
            st.error("Please enter a namespace.")
            st.stop()

        with st.spinner("Querying endorctl..."):
            df = run_analysis(namespace, days)

        st.session_state.df = df
        st.session_state.namespace = namespace
        st.session_state.days = days
        st.rerun()

    # --- Show results ---
    if st.session_state.df is None or st.session_state.df.empty:
        if st.session_state.df is not None:
            st.info("No results to display.")
        else:
            st.info("Configure the parameters in the sidebar and click **Generate Report**.")
        st.stop()

    df = st.session_state.df

    # --- Summary metrics ---
    st.markdown("## Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Block/Warn PRs", len(df))
    col2.metric("Blocked", len(df[df["outcome"] == "block"]))
    col3.metric("Warned", len(df[df["outcome"] == "warn"]))
    col4.metric("Projects Affected", df["project_name"].nunique())

    # --- Filters ---
    st.markdown("## Filters")
    fcol1, fcol2, fcol3 = st.columns(3)

    with fcol1:
        projects = ["All"] + sorted(df["project_name"].unique().tolist())
        selected_project = st.selectbox("Project", projects)

    with fcol2:
        outcomes = ["All", "block", "warn"]
        selected_outcome = st.selectbox("Outcome", outcomes)

    with fcol3:
        search = st.text_input("Search (PR URL, project name)", value="")

    filtered = df.copy()
    if selected_project != "All":
        filtered = filtered[filtered["project_name"] == selected_project]
    if selected_outcome != "All":
        filtered = filtered[filtered["outcome"] == selected_outcome]
    if search:
        mask = (
            filtered["pr_url"].str.contains(search, case=False, na=False)
            | filtered["project_name"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    st.caption(f"Showing {len(filtered)} of {len(df)} results")

    # --- Timeline chart ---
    st.markdown("## Timeline")

    if not filtered.empty and filtered["date"].notna().any():
        chart_df = filtered.copy()
        chart_df["day"] = chart_df["date"].dt.date

        daily = (
            chart_df.groupby(["day", "outcome"])
            .size()
            .reset_index(name="count")
        )

        chart = (
            alt.Chart(daily)
            .mark_bar()
            .encode(
                x=alt.X("day:T", title="Date"),
                y=alt.Y("count:Q", title="Count", stack=True),
                color=alt.Color(
                    "outcome:N",
                    scale=alt.Scale(
                        domain=["block", "warn"],
                        range=["#d32f2f", "#fbc02d"],
                    ),
                    title="Outcome",
                ),
                tooltip=["day:T", "outcome:N", "count:Q"],
            )
            .properties(height=350)
        )

        st.altair_chart(chart, use_container_width=True)

    # --- Top projects ---
    st.markdown("## Top Projects by Block/Warn Count")

    top_projects = (
        filtered.groupby("project_name")["outcome"]
        .value_counts()
        .unstack(fill_value=0)
        .assign(total=lambda x: x.sum(axis=1))
        .sort_values("total", ascending=False)
        .head(15)
    )

    if not top_projects.empty:
        display_cols = [c for c in ["block", "warn", "total"] if c in top_projects.columns]
        st.dataframe(top_projects[display_cols], use_container_width=True)

    # --- Data table ---
    st.markdown("## PR Scan Details")

    st.dataframe(
        filtered,
        use_container_width=True,
        height=500,
        column_config={
            "date": st.column_config.DatetimeColumn("Date", format="YYYY-MM-DD HH:mm"),
            "project_name": st.column_config.TextColumn("Project", width="medium"),
            "project_url": st.column_config.LinkColumn("Project Link", width="small"),
            "pr_url": st.column_config.LinkColumn("PR URL", width="medium"),
            "scan_result_url": st.column_config.LinkColumn("Scan Result", width="small"),
            "outcome": st.column_config.TextColumn("Outcome", width="small"),
            "blocker_findings": st.column_config.NumberColumn("Blockers", width="small"),
            "warning_findings": st.column_config.NumberColumn("Warnings", width="small"),
            "pr_check_conclusion": st.column_config.TextColumn("Conclusion", width="small"),
        },
    )

    # --- Export ---
    st.markdown("## Export")

    csv_data = filtered.to_csv(index=False)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    st.download_button(
        label="Download CSV",
        data=csv_data,
        file_name=f"pr_block_warn_{st.session_state.namespace}_{ts}.csv",
        mime="text/csv",
        use_container_width=True,
    )


if __name__ == "__main__":
    main()
