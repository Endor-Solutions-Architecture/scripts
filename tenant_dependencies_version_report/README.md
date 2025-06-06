# Tenant Dependencies Version Report

This script generates a CSV report of all unique dependencies and their versions across all projects in a specified namespace using the Endor Labs API. It also identifies outdated dependencies based on findings from a specific policy. The script can analyze either the entire tenant or a specific project.

## Features

- Fetches dependency metadata for the namespace or specific project
- Identifies outdated dependencies using policy findings
- Extracts dependency versions and update information
- Exports results to a timestamped CSV file in the generated_reports directory
- Supports both API key/secret and token authentication
- Supports project-specific analysis with optional branch filtering

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

## Usage

The script supports the following command-line options:

- `--project-uuid, -p`: Project UUID to analyze (optional)
- `--branch-name, -b`: Branch name to analyze (requires --project-uuid)
- `--help`: Show help menu

You have several options to run the script:

1. Analyze entire tenant:
   ```bash
   npm start
   ```

2. Analyze specific project:
   ```bash
   npm start -- --project-uuid your_project_uuid
   # or using the short form
   npm start -- -p your_project_uuid
   ```

3. Analyze specific project with branch:
   ```bash
   npm start -- --project-uuid your_project_uuid --branch-name your_branch
   # or using the short form
   npm start -- -p your_project_uuid -b your_branch
   ```

4. Build and run in one command:
   ```bash
   # Any of the above commands can be used with npm run all
   npm run all -- --project-uuid your_project_uuid --branch-name your_branch
   ```

The script will:
1. Authenticate with the Endor Labs API
2. Fetch dependency metadata (for tenant or specific project)
3. Fetch findings for outdated dependencies
4. Process and combine the data
5. Create a directory named `generated_reports` if it doesn't exist
6. Create a timestamped CSV file with the pattern:
   - Tenant-wide: `{namespace}_dependency_versions_YYYY-MM-DD-HH-MM-SS.csv`
   - Project without branch: `{namespace}_{project_uuid}_main_dependency_versions_YYYY-MM-DD-HH-MM-SS.csv`
   - Project with branch: `{namespace}_{project_uuid}_{branch_name}_dependency_versions_YYYY-MM-DD-HH-MM-SS.csv`

## Available Commands

- `npm run build` - Installs dependencies for both this project and endor_common
- `npm start [-- options]` - Runs the script with optional parameters
- `npm run all [-- options]` - Builds the project and runs the script in sequence

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