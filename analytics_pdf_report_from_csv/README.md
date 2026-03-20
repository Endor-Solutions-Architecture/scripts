# Analytics PDF Report Generator

Generate a dashboard-style PDF report from an Endor Labs analytics JSON export.

## Overview

The Endor Labs UI allows generating analytics reports as JSON exports, but there is no way to view or share the data as a formatted document. This script takes the exported JSON and produces a PDF with charts and summary cards that mirror the analytics dashboard.

### Report sections

- **Vulnerabilities Snapshot** — summary cards (newly discovered, resolved, mean/min/max time to resolve)
- **Vulnerabilities Over Time** — line chart of newly discovered vs resolved findings
- **Severity Breakdown** — stacked area chart of newly discovered findings by severity
- **Time for Vulnerabilities Issues Resolved** — line chart of average/min/max resolution time

## Prerequisites

- Python 3.11+
- The analytics JSON export from Endor Labs (UI → Analytics → Create Report → download)

## Setup

```bash
cd analytics_pdf_report_from_csv
pip install -r requirements.txt
```

## Usage

```bash
# Basic — output goes to generated_reports/
python main.py -f /path/to/analytics_report.json

# Custom output path
python main.py -f /path/to/analytics_report.json -o my_report.pdf
```

## Output

The generated PDF is saved to `generated_reports/analytics_report_<timestamp>.pdf` by default, or to the path specified with `-o`.
