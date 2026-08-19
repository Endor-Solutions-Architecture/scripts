# Endor Labs Dependency Search Tool

This repository contains a Python script for searching dependencies using the Endor Labs API. The script finds which projects use specific dependencies under `ENDOR_NAMESPACE` and all of its child namespaces.

### Prerequisites

- Python 3.6+
- Required Python packages: `requests`, `python-dotenv`
- Endor Labs API key and secret

### Installation

1. Installation:
   ```
   python3 -m venv venv
   source venv/bin/activate  # On Windows use `venv\\Scripts\\activate`
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the same directory as the script with your Endor Labs API credentials and fill these values or copy paste from env_template:
   ```
   API_KEY=<YOUR_KEY>
   API_SECRET=<YOUR_SECRET>
   ENDOR_NAMESPACE="<YOUR_TENANT_NAMESPACE>"
   ```

## Usage

### Dependency Search (`search_dependencies.py`)

Searches for specific dependencies under your configured namespace and all child namespaces, and finds which projects use them. The script searches only the main context and outputs results to the terminal, JSON, and CSV formats.

#### Examples

Search for a single dependency:
```
python search_dependencies.py --dependencies "npm://lodash@4.17.21"
```

Search for multiple dependencies:
```
python search_dependencies.py --dependencies "npm://@graphql-tools/wrap@10.1.4,pypi://typing-extensions@4.12.2"
```

#### Dependency Format

Dependencies must be specified in the format: `ecosystem://dependency@version`

Examples:
- `npm://lodash@4.17.21`
- `npm://@graphql-tools/wrap@10.1.4`
- `maven://org.springframework:spring-core@5.3.21`
- `pypi://typing-extensions@4.12.2`

#### Output Files

The script generates timestamped output files:
- `dependency_search_results_YYYYMMDD_HHMMSS.json` - Complete results in JSON format
- `dependency_search_results_YYYYMMDD_HHMMSS.csv` - Results in CSV format for easy analysis

#### Features

- **Cross-namespace search**: Lists namespace FQDNs under `ENDOR_NAMESPACE` (ListNamespaces subtree traverse), then queries **DependencyMetadata per namespace FQDN** with no `traverse` on the query. Each row uses the FQDN from the URL path
- **Main context only**: Focuses on production dependencies (excludes test/dev contexts)
- **Multiple output formats**: Terminal display, JSON, and CSV
- **Detailed results**: Includes project name (with git URL), dependency scope, and parent package version information

