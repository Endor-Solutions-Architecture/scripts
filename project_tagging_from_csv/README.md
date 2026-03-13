# Project Tagging from CSV

Bulk-apply tags to projects in [Endor Labs](https://www.endorlabs.com/) by reading a simple CSV file.

## Prerequisites

- Python 3.8+
- An Endor Labs account with access to the target namespace
- **One** of the following for authentication:
  - [`endorctl`](https://docs.endorlabs.com/endorctl/) CLI installed (recommended), **or**
  - An Endor Labs API key and secret

## Quick Start

```bash
# 1. Set up a virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Authenticate (pick one)

#    Option A – endorctl token (recommended, no .env needed)
export ENDOR_TOKEN="$(endorctl auth --print-access-token)"

#    Option B – API key/secret via .env file
cp .env.example .env
#    Then edit .env and fill in API_KEY and API_SECRET

# 3. Run
python3 project_tags.py --namespace <your_namespace> --gitorg <your_git_org> projects.csv
```

## Authentication

The script resolves a bearer token using the following precedence:

| Priority | Method | How to set |
|----------|--------|------------|
| 1 | `ENDOR_TOKEN` env var | `export ENDOR_TOKEN="$(endorctl auth --print-access-token)"` |
| 2 | API key / secret | Set `API_KEY` and `API_SECRET` in a `.env` file |

Using `ENDOR_TOKEN` is recommended because it leverages your existing `endorctl` session — no need to create and manage long-lived API credentials.

## Configuration

**Namespace** and **Git org** can be provided in two ways. CLI flags take precedence over environment variables.

| Parameter | CLI Flag | Env Var |
|-----------|----------|---------|
| Namespace | `--namespace` | `ENDOR_NAMESPACE` |
| Git org | `--gitorg` | `GITORG` |

## CSV Format

The CSV file should have **no header row** and two columns:

| Column | Description |
|--------|-------------|
| 1 | Project name (without the git org prefix) |
| 2 | Tag(s), comma-separated |

**Example:**

```csv
project-alpha,security
project-beta,
project-gamma,"data_team,platform"
```

> **Note:** Do not include the git org in the project name — it is automatically prepended using the `--gitorg` value (e.g., `my-org/project-alpha`).

> **Note:** Multi-word tags are automatically converted to use underscores (e.g., `PRO Team` → `PRO_Team`). Existing tags on a project are preserved; new tags are merged without duplicates.

## Usage Examples

```bash
# Inline parameters
python3 project_tags.py --namespace acme.gh-acme --gitorg acme projects.csv

# Using environment variables (from .env or exported)
export ENDOR_NAMESPACE="acme.gh-acme"
export GITORG="acme"
python3 project_tags.py projects.csv

# Mix: env var for auth, CLI flags for namespace/org
export ENDOR_TOKEN="$(endorctl auth --print-access-token)"
python3 project_tags.py --namespace acme.gh-acme --gitorg acme projects.csv
```
