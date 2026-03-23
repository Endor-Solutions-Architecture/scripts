---
name: generate-remediation-report
description: Run the remediated findings report script for Endor Labs
argument-hint: "[--start-date YYYY-MM-DD --end-date YYYY-MM-DD --output file.csv]"
---

Help the user run the `remediated_findings_report/generate_remediation_report.py` script. Follow these steps:

## 1. Collect parameters

If $ARGUMENTS contains the needed flags, parse them directly. Otherwise ask the user for:

**Required:**
- `--start-date` — report start date in `YYYY-MM-DD` format
- `--end-date` — report end date in `YYYY-MM-DD` format
- `--output` — output CSV file path (suggest a default like `report_<start>_to_<end>.csv`)

**Optional (ask if they want to filter or tune performance):**
- `--project-uuid` — restrict findings to a single project UUID
- `--batch-size` — package_version UUIDs per API request (default: 100)

## 2. Check environment setup

Before running, verify:

1. A `.env` file exists at `remediated_findings_report/.env` OR the required env vars are exported. The script needs either:
   - `ENDOR_TOKEN` + `ENDOR_NAMESPACE`, or
   - `API_KEY` + `API_SECRET` + `ENDOR_NAMESPACE`

   If missing, inform the user and show them the required `.env` format:
   ```
   ENDOR_NAMESPACE=<your_namespace>
   ENDOR_TOKEN=<your_token>        # set this OR the pair below
   API_KEY=<your_api_key>          # optional if ENDOR_TOKEN is set
   API_SECRET=<your_api_secret>    # optional if ENDOR_TOKEN is set
   ```

2. A virtual environment exists at `remediated_findings_report/.venv/`. If not, guide the user to create it:
   ```bash
   cd remediated_findings_report
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## 3. Run the script

Activate the venv and run from the `remediated_findings_report/` directory:

```bash
cd remediated_findings_report && source .venv/bin/activate && python generate_remediation_report.py --start-date <start> --end-date <end> --output <output> [--project-uuid <uuid>] [--batch-size <n>]
```

## 4. Report results

After the script finishes:
- If successful, confirm the output CSV path and the number of rows written.
- If it fails, show the error and help diagnose: auth failure, invalid date format, API error, missing namespace, etc.
