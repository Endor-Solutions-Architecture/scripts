# Tenant Dependencies Version Report

This script generates a CSV report of all unique dependencies and their versions across all projects in a specified namespace using the Endor Labs API. It also identifies outdated dependencies based on findings from a specific policy.

## Features

- Fetches dependency metadata for the namespace
- Identifies outdated dependencies using policy findings
- Extracts dependency versions and update information
- Exports results to a timestamped CSV file in the generated_reports directory
- Supports both API key/secret and token authentication

## Prerequisites

- Node.js (v14 or higher)
- npm (Node Package Manager)
- Access to Endor Labs API
- UUID of the outdated dependencies policy

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
5. Configure your .env file with one of these authentication methods and required variables:

   **Option 1: Using API Key and Secret**
   ```
   API_KEY=your_api_key_here
   API_SECRET=your_api_secret_here
   NAMESPACE=your_namespace_here
   OUTDATED_POLICY_UUID=your_policy_uuid_here
   ```

   **Option 2: Using API Token**
   ```
   API_TOKEN=your_api_token_here
   NAMESPACE=your_namespace_here
   OUTDATED_POLICY_UUID=your_policy_uuid_here
   ```

## Required Environment Variables

- `API_TOKEN` or (`API_KEY` and `API_SECRET`): For authentication
- `NAMESPACE`: The namespace to analyze
- `OUTDATED_POLICY_UUID`: UUID of the policy that identifies outdated dependencies

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
3. Fetch findings for outdated dependencies
4. Process and combine the data
5. Create a directory named `generated_reports` if it doesn't exist
6. Create a timestamped CSV file named `{namespace}_dependency_versions_YYYY-MM-DD-HH-MM-SS.csv` in the generated_reports directory

## Available Commands

- `npm run build` - Installs dependencies for both this project and endor_common
- `npm start` - Runs the script
- `npm run all` - Builds the project and runs the script in sequence

## Output

The generated CSV file contains:
- Ecosystem: Package ecosystem (e.g., "npm", "gem")
- Dependency: Package name
- Version: Current version
- Dependent Packages: Number of packages that depend on this package
- Is Outdated: Whether the package has an available update (true/false)
- Latest Release: Latest available version (if outdated)
- Releases Behind: Number of releases behind the latest version (if outdated)

Example:
```
Ecosystem,Dependency,Version,Dependent Packages,Is Outdated,Latest Release,Releases Behind
"npm","debug","2.6.9",5,true,"4.3.4",13
"npm","lodash","4.17.21",12,false,"",
```

## Notes

- Duplicate dependencies (same name and version) are only included once
- The script uses the Endor Labs dependency metadata API
- Outdated package information comes from a specific policy finding
- The script shows a summary of total dependencies and how many are outdated.