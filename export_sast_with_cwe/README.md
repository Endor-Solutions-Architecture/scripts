# SAST Findings CSV Export with CWE Field

This is a Python script that exports **SAST findings** from Endor Labs into a CSV file, with the **CWE column populated** from the SAST rule metadata. It's intended as a drop-in replacement for the standard SAST Findings export when you specifically need CWE values for SAST since the platform export doesn't include the CWE column.

---

## What the script does

- Uses **endorctl** to query the Endor Labs **Finding** API.
- Traverses a **root namespace and all child namespaces**.
- Collects all **non-exception SAST findings** for every project in scope.
- Reads CWE information from `spec.finding_metadata.custom.cwes`.
- Writes a CSV similar to the UI Findings export, but with **CWE filled for SAST**.

---

## Prerequisites

- **Python 3.8+**
- **endorctl** installed and authenticated

---

## Usage

```bash
python export_sast_with_cwe.py -n <namespace> -o <output.csv>
```

| Flag | Description |
|------|-------------|
| `-n, --namespace` | Root namespace to traverse |
| `-o, --output` | Output CSV file name |

**Example:**

```bash
python export_sast_with_cwe.py -n mynamespace -o sast-findings-with-cwe.csv
```

---

## Output

The CSV includes these columns:

- UUID
- Title
- Severity Level
- Attributes
- Finding Categories
- Remediation
- Fix Version
- Risk Details
- Explanation
- CVE
- **CWE** ← populated from SAST rule metadata
- Project Name
