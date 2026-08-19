# Endor Labs SBOM Generator

This repository contains a script for interacting with the Endor Labs API to generate Software Bill of Materials (SBOM) files in SPDX format.

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
   ENDOR_NAMESPACE="<YOUR_PARENT_NAMESPACE>"
   ORGANIZATION="<YOUR_ORGANIZATION>"
   PERSON_EMAIL="<YOUR_EMAIL>"
   ```

#### Examples

Generate SPDX SBOM:
```
python create_spdx_sbom.py --project_uuid <your_project_uuid>
```
