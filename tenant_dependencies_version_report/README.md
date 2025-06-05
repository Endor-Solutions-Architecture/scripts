# Tenant Dependencies Version Report

This script generates a CSV report of all unique dependencies and their versions across all projects in a specified namespace using the Endor Labs API.

## Features

- Fetches dependency metadata for the namespace
- Filters for MAIN and SBOM context types
- Extracts unique dependencies and their versions
- Exports results to a timestamped CSV file in the generated_reports directory
- Supports both API key/secret and token authentication

## Prerequisites

- Node.js (v14 or higher)
- npm (Node Package Manager)
- Access to Endor Labs API

## Setup

1. Clone the repository
2. Navigate to the script directory:
   ```bash
   cd tenant_dependencies_version_report
   ```
3. Build the project (this will install dependencies for both this project and endor_common):
   ```bash
   npm run build
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

You have several options to run the script:

1. After initial setup, run just the script:
   ```bash
   npm start
   ```

2. Build and run in one command (useful after pulling updates):
   ```bash
   npm run all
   ```

The script will:
1. Authenticate with the Endor Labs API
2. Fetch dependency metadata for the namespace
3. Filter and process dependencies
4. Create a directory named `generated_reports` if it doesn't exist
5. Create a timestamped CSV file named `{namespace}_dependency_versions_YYYY-MM-DD-HH-MM-SS.csv` in the generated_reports directory

## Available Commands

- `npm run build` - Installs dependencies for both this project and endor_common
- `npm start` - Runs the script
- `npm run all` - Builds the project and runs the script in sequence

## Output

The generated CSV file contains:
- Package: Full package identifier (e.g. "pkg:npm/axios@1.6.2")
- Name: Package name
- Version: Package version
- Type: Context type (CONTEXT_TYPE_MAIN, CONTEXT_TYPE_SBOM, or UNKNOWN)

Example:
```
Package,Name,Version,Type
"pkg:npm/axios@1.6.2","axios","1.6.2","CONTEXT_TYPE_MAIN"
"pkg:npm/dotenv@16.3.1","dotenv","16.3.1","CONTEXT_TYPE_SBOM"
```

## Error Handling

- The script validates required environment variables
- Handles API errors gracefully
- Provides clear error messages for troubleshooting

## Notes

- Duplicate dependencies (same name and version) are only included once
- The script uses the Endor Labs dependency metadata API
- Results are filtered to include only MAIN and SBOM context types
- All results are written to timestamped files in the generated_reports directory 