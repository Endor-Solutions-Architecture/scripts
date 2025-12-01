#!/usr/bin/env python3
"""
Audit Log Report Generator - Streamlit App

This script orchestrates the Endor CLI to collect and analyze audit log data
for user navigation and user actions using Streamlit for interactive visualizations.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import re

import streamlit as st
import pandas as pd


def get_audit_logs(namespace: str, date_range: str, report_type: str, email_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get audit logs for the specified namespace, date range, and report type."""
    st.info(f"Getting {report_type} audit logs for date range: {date_range}")
    
    # Calculate the cutoff time based on date_range (support both days and hours)
    time_map = {
        "1D": 1, "2D": 2, "3D": 3, "4D": 4, "5D": 5, "6D": 6, "7D": 7, "15D": 15, "30D": 30,
        "1H": 1, "2H": 2, "4H": 4, "6H": 6, "8H": 8, "12H": 12
    }
    
    # Map report types to message kinds
    message_kind_map = {
        "User Navigation": "internal.endor.ai.endor.v1.UITelemetry",
        "User Actions": "internal.endor.ai.endor.v1.UserTelemetry"
    }
    
    message_kind = message_kind_map.get(report_type)
    if not message_kind:
        st.error(f"Unknown report type: {report_type}")
        return []
    
    # Get the time value and determine if it's hours or days
    if date_range.endswith('H'):
        # Hours - use timestamp comparison for precision
        hours = time_map.get(date_range, 1)
        # Use UTC time to avoid timezone issues
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        timestamp_rfc = cutoff_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        st.info(f"Cutoff time (hours) UTC: {timestamp_rfc}")
    else:
        # Days - use date comparison
        days = time_map.get(date_range, 1)
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        timestamp_rfc = cutoff_date
        st.info(f"Cutoff date (days) UTC: {cutoff_date}")
    
    # Build filter expression
    if email_filter and email_filter.strip():
        filter_expr = f'spec.claims matches ".*{email_filter.strip()}.*" and spec.message_kind=="{message_kind}" and meta.create_time > date("{timestamp_rfc}")'
    else:
        filter_expr = f'spec.message_kind=="{message_kind}" and meta.create_time > date("{timestamp_rfc}")'
    
    cmd = [
        "endorctl", "api", "list", "-r", "AuditLog", "-n", namespace,
        "--filter", filter_expr,
        "--field-mask", "spec.message_kind,spec.claims,spec.payload",
        "--list-all", "-t", "300s", "--traverse"
    ]
    
    # Debug: Show the exact command being run
    st.info(f"Running command: {' '.join(cmd)}")
    print(f"[AUDIT LOG] Running endorctl command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"[AUDIT LOG] Command completed successfully. Response length: {len(result.stdout)} chars")
        st.info(f"Command stdout length: {len(result.stdout)}")
        st.info(f"Command stderr length: {len(result.stderr)}")
        
        if result.stdout.strip():
            data = json.loads(result.stdout)
            audit_logs = data.get("list", {}).get("objects", [])
            st.success(f"Found {len(audit_logs)} audit log entries")
            
            # Debug: Show first few entries to see the structure
            if audit_logs:
                first_entry = audit_logs[0]
                st.info(f"Sample entry structure: {list(first_entry.keys())}")
            
            return audit_logs
        else:
            st.warning("No stdout from command - this might indicate an issue")
            return []
    except subprocess.CalledProcessError as e:
        print(f"[AUDIT LOG] Command failed with error: {e}")
        print(f"[AUDIT LOG] stderr: {e.stderr}")
        st.error(f"Error getting audit logs: {e}")
        st.error(f"stderr: {e.stderr}")
        return []
    except json.JSONDecodeError as e:
        print(f"[AUDIT LOG] JSON parsing error: {e}")
        st.error(f"Error parsing audit logs response: {e}")
        return []


def extract_claims_info(claims: List[str]) -> Dict[str, str]:
    """Extract structured information from claims list."""
    claims_info = {}
    for claim in claims:
        if '=' in claim:
            key, value = claim.split('=', 1)
            claims_info[key] = value
        else:
            claims_info[claim] = claim
    return claims_info


def process_ui_telemetry_data(audit_logs: List[Dict[str, Any]]) -> pd.DataFrame:
    """Process UI Telemetry data into a DataFrame."""
    processed_data = []
    
    for log_entry in audit_logs:
        spec = log_entry.get("spec", {})
        payload = spec.get("payload", {})
        payload_spec = payload.get("spec", {})
        events = payload_spec.get("events", [])
        tenant_meta = payload.get("tenant_meta", {})
        claims = spec.get("claims", [])
        
        # Extract claims information
        claims_info = extract_claims_info(claims)
        
        # Process each event
        for event in events:
            processed_data.append({
                "namespace": tenant_meta.get("namespace", ""),
                "date": event.get("timestamp", ""),
                "email": claims_info.get("email", ""),
                "claims": json.dumps(claims_info),
                "event": event.get("key", ""),
                "value": event.get("value", ""),
                "domain": claims_info.get("domain", ""),
                "browser": payload_spec.get("device_user_agent", {}).get("browser_name", ""),
                "os": payload_spec.get("device_user_agent", {}).get("os_name", "")
            })
    
    return pd.DataFrame(processed_data)


def process_user_telemetry_data(audit_logs: List[Dict[str, Any]]) -> pd.DataFrame:
    """Process User Telemetry data into a DataFrame."""
    processed_data = []
    
    for log_entry in audit_logs:
        spec = log_entry.get("spec", {})
        payload = spec.get("payload", {})
        payload_spec = payload.get("spec", {})
        event_store = payload_spec.get("event_store", {})
        tenant_meta = payload.get("tenant_meta", {})
        claims = spec.get("claims", [])
        meta = payload.get("meta", {})
        
        # Extract claims information
        claims_info = extract_claims_info(claims)
        
        # Process each event in the event store
        for event_key, event_data in event_store.items():
            if isinstance(event_data, dict):
                processed_data.append({
                    "namespace": tenant_meta.get("namespace", ""),
                    "date": meta.get("create_time", ""),
                    "email": claims_info.get("email", ""),
                    "claims": json.dumps(claims_info),
                    "event": event_key,
                    "value": event_data.get("value", ""),
                    "timestamp": event_data.get("timestamp", ""),
                    "domain": claims_info.get("domain", ""),
                    "properties": json.dumps(event_data.get("properties", {}))
                })
    
    return pd.DataFrame(processed_data)


def save_data(audit_logs: List[Dict[str, Any]], df: pd.DataFrame, output_dir: str, report_type: str) -> None:
    """Save raw data and processed DataFrame."""
    st.info("Saving data...")
    
    # Create data subdirectory
    data_dir = os.path.join(output_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    # Save raw audit logs
    with open(os.path.join(data_dir, f"raw_audit_logs_{report_type.lower().replace(' ', '_')}.json"), 'w') as f:
        json.dump(audit_logs, f, indent=2)
    
    # Save processed DataFrame as CSV
    csv_filename = f"processed_audit_logs_{report_type.lower().replace(' ', '_')}.csv"
    df.to_csv(os.path.join(data_dir, csv_filename), index=False)
    
    st.success(f"Data saved to {data_dir}")


def create_filtered_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Create a filtered and sortable DataFrame for display."""
    if df.empty:
        return df
    
    # Create a copy for filtering
    filtered_df = df.copy()
    
    # Convert date column to datetime for better sorting
    if 'date' in filtered_df.columns:
        filtered_df['date'] = pd.to_datetime(filtered_df['date'], errors='coerce')
    
    return filtered_df


def main():
    """Main Streamlit app."""
    st.set_page_config(
        page_title="Audit Log Report",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    if 'show_results' not in st.session_state:
        st.session_state.show_results = False
    if 'current_results' not in st.session_state:
        st.session_state.current_results = None
    if 'filter_state' not in st.session_state:
        st.session_state.filter_state = {
            'search_term': '',
            'selected_event': '',
            'selected_email': '',
            'selected_namespace': ''
        }
    
    st.title("📋 Audit Log Report")
    st.markdown("---")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        
        # Check if endorctl is available
        try:
            subprocess.run(["endorctl", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            st.success("✅ endorctl available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            st.error("❌ endorctl not available")
            st.stop()
        
        # Input parameters
        namespace = st.text_input("Namespace", value="", help="Tenant namespace to analyze")
        
        report_type = st.selectbox(
            "Report Type",
            options=["User Navigation", "User Actions"],
            help="Type of audit log report to generate"
        )
        
        date_range = st.selectbox(
            "Date Range",
            options=["1H", "2H", "4H", "6H", "8H", "12H", "1D", "2D", "3D", "4D", "5D", "6D", "7D", "15D", "30D"],
            index=6,  # Default to 1D
            help="Date range for audit logs"
        )
        
        email_filter = st.text_input(
            "Email/Group Filter (Optional)", 
            value="", 
            help="Filter by specific email or group (optional)"
        )
        
        # Generate Report button
        generate_report = st.button("Generate Report", type="primary", use_container_width=True)
    
    # Main content area
    main_content = st.container()
    
    if not generate_report and not st.session_state.show_results:
        # Clear any previous content and show initial state
        with main_content:
            st.info("👈 Configure the parameters in the sidebar and click 'Generate Report' to start")
        st.stop()
    
    if not namespace:
        with main_content:
            st.error("Please enter a namespace")
        st.stop()
    
    # Check if we should run analysis
    should_run_analysis = generate_report or st.session_state.get('run_analysis', False)
    
    # If Generate Report was clicked, perform analysis and store results
    if should_run_analysis:
        # Smart reset: Clear any previous results when starting new analysis
        if st.session_state.show_results and not st.session_state.get('run_analysis', False):
            # First time clicking with previous results - clear and store intent
            st.session_state.clear()
            st.session_state.run_analysis = True  # Store intent for next run
            st.rerun()
        
        # Clear the stored intent (we're about to run analysis)
        if 'run_analysis' in st.session_state:
            del st.session_state.run_analysis
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Step 1: Get audit logs
            status_text.text("Getting audit logs...")
            progress_bar.progress(50)
            audit_logs = get_audit_logs(namespace, date_range, report_type, email_filter)
            
            if not audit_logs:
                st.warning("No audit logs found for the specified criteria.")
                st.stop()
            
            # Step 2: Process data
            status_text.text("Processing data...")
            progress_bar.progress(75)
            print(f"[AUDIT LOG] Processing {len(audit_logs)} audit log entries for {report_type}")
            
            if report_type == "User Navigation":
                df = process_ui_telemetry_data(audit_logs)
            else:  # User Actions
                df = process_user_telemetry_data(audit_logs)
            
            print(f"[AUDIT LOG] Processed data into {len(df)} records")
            
            # Step 3: Save data
            status_text.text("Saving data...")
            progress_bar.progress(90)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"generated_reports/{namespace}_audit_logs_{timestamp}"
            save_data(audit_logs, df, output_dir, report_type)
            
            # Complete progress
            progress_bar.progress(100)
            status_text.text("Analysis completed!")
            st.success("✅ Analysis completed successfully!")
            
            # Store results in session state
            st.session_state.current_results = {
                'audit_logs': audit_logs,
                'df': df,
                'output_dir': output_dir,
                'namespace': namespace,
                'report_type': report_type,
                'date_range': date_range,
                'email_filter': email_filter
            }
            st.session_state.show_results = True
            
            # Reset filter state for new data
            st.session_state.filter_state = {
                'search_term': '',
                'selected_event': '',
                'selected_email': '',
                'selected_namespace': ''
            }
            
            # Rerun to show results
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error during analysis: {e}")
            st.exception(e)
            st.stop()
    
    # Display results from session state
    if st.session_state.show_results and st.session_state.current_results:
        results = st.session_state.current_results
        
        # Display results in the main content container
        with main_content:
            st.markdown("## 📊 Results Summary")
            
            # Summary statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Log Entries", len(results['audit_logs']))
            with col2:
                st.metric("Processed Records", len(results['df']))
            with col3:
                st.metric("Report Type", results['report_type'])
            with col4:
                st.metric("Date Range", results['date_range'])
            
            # Show filter info if applied
            if results['email_filter']:
                st.info(f"🔍 Filtered by: {results['email_filter']}")
            
            # Data table section
            st.markdown("## 📋 Audit Log Data")
            
            if not results['df'].empty:
                # Create filtered dataframe
                filtered_df = create_filtered_dataframe(results['df'])
                
                # Add filtering controls
                st.markdown("### 🔍 Filter Data")
                
                # Search functionality
                search_term = st.text_input(
                    "🔍 Search in all columns", 
                    value=st.session_state.filter_state['search_term'],
                    placeholder="Enter search term...",
                    key="search_input"
                )
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # Event filter
                    unique_events = [''] + sorted(filtered_df['event'].unique().tolist())
                    selected_event = st.selectbox(
                        "Filter by Event", 
                        unique_events,
                        index=unique_events.index(st.session_state.filter_state['selected_event']) if st.session_state.filter_state['selected_event'] in unique_events else 0,
                        key="event_filter"
                    )
                
                with col2:
                    # Email filter
                    unique_emails = [''] + sorted([email for email in filtered_df['email'].unique() if email])
                    selected_email = st.selectbox(
                        "Filter by Email", 
                        unique_emails,
                        index=unique_emails.index(st.session_state.filter_state['selected_email']) if st.session_state.filter_state['selected_email'] in unique_emails else 0,
                        key="email_filter"
                    )
                
                with col3:
                    # Namespace filter
                    unique_namespaces = [''] + sorted(filtered_df['namespace'].unique().tolist())
                    selected_namespace = st.selectbox(
                        "Filter by Namespace", 
                        unique_namespaces,
                        index=unique_namespaces.index(st.session_state.filter_state['selected_namespace']) if st.session_state.filter_state['selected_namespace'] in unique_namespaces else 0,
                        key="namespace_filter"
                    )
                
                # Update session state with current filter values
                st.session_state.filter_state.update({
                    'search_term': search_term,
                    'selected_event': selected_event,
                    'selected_email': selected_email,
                    'selected_namespace': selected_namespace
                })
                
                # Apply filters
                display_df = filtered_df.copy()
                
                if selected_event:
                    display_df = display_df[display_df['event'] == selected_event]
                
                if selected_email:
                    display_df = display_df[display_df['email'] == selected_email]
                
                if selected_namespace:
                    display_df = display_df[display_df['namespace'] == selected_namespace]
                
                # Apply search filter
                if search_term:
                    # Search across all string columns
                    search_mask = pd.Series([False] * len(display_df))
                    for col in display_df.columns:
                        if display_df[col].dtype == 'object':  # String columns
                            search_mask |= display_df[col].astype(str).str.contains(
                                search_term, case=False, na=False
                            )
                    display_df = display_df[search_mask]
                
                # Show filter results and clear button
                col1, col2 = st.columns([3, 1])
                with col1:
                    if len(display_df) != len(filtered_df):
                        st.info(f"Showing {len(display_df)} of {len(filtered_df)} records")
                    else:
                        st.info(f"Showing all {len(display_df)} records")
                
                with col2:
                    if st.button("Clear Filters", help="Reset all filters"):
                        # Reset filter state
                        st.session_state.filter_state = {
                            'search_term': '',
                            'selected_event': '',
                            'selected_email': '',
                            'selected_namespace': ''
                        }
                        st.rerun()
                
                # Display the filtered dataframe
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    height=600,
                    column_config={
                        "date": st.column_config.DatetimeColumn(
                            "Date",
                            format="YYYY-MM-DD HH:mm:ss",
                            width="medium"
                        ),
                        "claims": st.column_config.TextColumn(
                            "Claims",
                            width="large"
                        ),
                        "value": st.column_config.TextColumn(
                            "Value",
                            width="large"
                        ),
                        "event": st.column_config.TextColumn(
                            "Event",
                            width="medium"
                        ),
                        "email": st.column_config.TextColumn(
                            "Email",
                            width="medium"
                        ),
                        "namespace": st.column_config.TextColumn(
                            "Namespace",
                            width="small"
                        )
                    }
                )
                
                # Export functionality
                st.markdown("## 💾 Export Data")
                
                # Get the current filtered data (what's visible in the table)
                csv_data = display_df.to_csv(index=False)
                
                st.download_button(
                    label="📥 Download CSV",
                    data=csv_data,
                    file_name=f"audit_logs_{results['report_type'].lower().replace(' ', '_')}_{results['namespace']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
                # Show data directory info
                st.info(f"📁 Raw data and processed files saved to: `{results['output_dir']}`")
                
                # Show file structure
                with st.expander("📁 Generated Files"):
                    st.code(f"""
{results['output_dir']}/
├── data/
│   ├── raw_audit_logs_{results['report_type'].lower().replace(' ', '_')}.json
│   └── processed_audit_logs_{results['report_type'].lower().replace(' ', '_')}.csv
└── (Streamlit app data)
                    """)
                
            else:
                st.warning("No data to display")
            
            # Show sample of raw data for debugging
            with st.expander("🔍 Raw Data Sample (First Entry)"):
                if results['audit_logs']:
                    st.json(results['audit_logs'][0])
                else:
                    st.info("No raw data available")


if __name__ == "__main__":
    main()
