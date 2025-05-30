# Tenant Dependency License Report

This script generates a CSV report of all unique dependencies and their licenses across all projects in a specified namespace using the Endor Labs API.

## Features

- Fetches all projects in a namespace
- Generates SBOM data for each project
- Extracts unique dependencies and their licenses
- Exports results to a CSV file
- Supports both API key/secret and token authentication

## Prerequisites

- Node.js (v14 or higher)
- npm (Node Package Manager)
- Access to Endor Labs API

## Setup

1. Clone the repository
2. Navigate to the script directory:
   ```bash
   cd tenant_dependency_license_report
   ```
3. Install dependencies:
   ```bash
   npm install
   ```
4. Copy the environment template:
   ```bash
   cp .env.example .env
   ```
5. Configure your .env file with one of these authentication methods:

   **Option 1: Using API Key and Secret**
   ```
   API_KEY=your_api_key_here
   API_SECRET=your_api_secret_here
   ENDOR_NAMESPACE=your_namespace_here
   ```

   **Option 2: Using API Token**
   ```
   API_TOKEN=your_api_token_here
   ENDOR_NAMESPACE=your_namespace_here
   ```

## Authentication Methods

The script supports two authentication methods:

1. **API Token**
   - Provide a pre-generated API token in the .env file
   - Token is used directly for API calls
   - Useful when you already have a valid token
   - Takes precedence over API key/secret if both are provided

2. **API Key and Secret**
   - Provide both API key and secret in the .env file
   - Script automatically generates a token
   - Used as fallback when no API token is provided

## Usage

Run the script:
```bash
npm start
```

The script will:
1. Authenticate with the Endor Labs API
2. Fetch all projects in the specified namespace
3. Generate SBOM data for each project
4. Extract unique dependencies and their licenses
5. Create a CSV file named `{namespace}_dependency_license.csv`

## Output

The generated CSV file contains:
- Name: Package name
- Version: Package version
- License: License name (or "No License" if not specified)

Example:
```
Name,Version,License
"axios","1.6.2","MIT"
"dotenv","16.3.1","BSD-2-Clause"
```

## Error Handling

- The script logs errors for individual project processing
- Continues processing remaining projects if one fails
- Displays a summary of processed projects and unique dependencies found

## Notes

- Duplicate dependencies (same name and version) are only included once
- Processing time depends on the number of projects in the namespace
- Large namespaces may take several minutes to process
- Limited to 500 projects per namespace (no pagination support at the moment)