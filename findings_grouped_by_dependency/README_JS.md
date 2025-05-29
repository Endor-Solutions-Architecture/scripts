# Findings Grouped by Dependency - JavaScript Script

This JavaScript script fetches findings from the Endor Labs API for a specific project and groups them by dependency package name.

## Prerequisites

- Node.js (version 14 or higher)
- npm (Node Package Manager)
- Endor Labs API credentials

## Installation

1. **Navigate to the script directory:**
   ```bash
   cd findings_grouped_by_dependency
   ```

2. **Install the required dependencies:**
   ```bash
   npm install
   ```

3. **Set up environment variables:**
   
   Copy the example environment file:
   ```bash
   cp env.example .env
   ```
   
   Edit the `.env` file with your actual API credentials:
   ```bash
   # Edit with your preferred editor
   nano .env
   # or
   code .env
   # or
   vim .env
   ```
   
   Add your credentials:
   ```
   API_KEY=your_actual_api_key_here
   API_SECRET=your_actual_api_secret_here
   ENDOR_NAMESPACE=your_namespace_here
   ```

## Usage

### Basic Usage

Run the script with a project UUID:

```bash
node script.js "your-project-uuid-here"
```

### Alternative Syntax

You can also use the flag syntax:

```bash
node script.js --project_uuid "your-project-uuid-here"
```

### Example

```bash
node script.js "6827702d546546c90d4e525d"
```

## Output

The script outputs clean JSON with findings grouped by dependency package:

```json
{
  "summary": {
    "namespace": "your-namespace",
    "projectUuid": "6827702d546546c90d4e525d",
    "totalFindings": 40,
    "totalDependencies": 15,
    "processedAt": "2024-01-15T10:30:00.000Z"
  },
  "dependencyGroups": [
    {
      "dependencyPackageName": "pypi://flask@1.0",
      "findingCount": 3,
      "uniqueDescriptions": [
        "License Compliance Violation for Dependency flask@1.0",
        "Outdated Dependency flask@1.0",
        "GHSA-m2qf-hxjv-5gpq: Flask vulnerable to possible disclosure..."
      ],
      "projectCount": 1,
      "descriptionCount": 3,
      "aggregationUuids": [
        "682771d3ba82306d0da7c7d8",
        "682771d369b45343a890d998",
        "682771d39c9bc4ee2d77d44d"
      ]
    }
  ]
}
```

## Output Processing

Since the script outputs clean JSON, you can easily process it with other tools:

### Save to file:
```bash
node script.js "project-uuid" > results.json
```

### Use with jq for filtering:
```bash
# Get total findings count
node script.js "project-uuid" | jq '.summary.totalFindings'

# Get dependency names only
node script.js "project-uuid" | jq '.dependencyGroups[].dependencyPackageName'

# Filter dependencies with more than 5 findings
node script.js "project-uuid" | jq '.dependencyGroups[] | select(.findingCount > 5)'
```

### Pipe to other scripts:
```bash
node script.js "project-uuid" | python process_findings.py
```

## What the Script Does

1. **Authenticates** with the Endor Labs API using your credentials
2. **Fetches findings** for the specified project using these filters:
   - Project UUID matches the provided UUID
   - Context type is `CONTEXT_TYPE_MAIN`
   - Excludes findings tagged with `FINDING_TAGS_EXCEPTION`
   - Only includes findings where `meta.parent_kind` is `PackageVersion`
   - Excludes findings tagged with `FINDING_TAGS_SELF`
3. **Groups findings** by `spec.target_dependency_package_name`
4. **Aggregates data** including:
   - Count of findings per dependency
   - Unique descriptions
   - Project and description counts
   - Aggregation UUIDs
5. **Outputs clean JSON** for easy processing

## Error Handling

- **Missing credentials**: Script will exit with an error if API_KEY, API_SECRET, or ENDOR_NAMESPACE are not set
- **Invalid project UUID**: Script will exit if no project UUID is provided
- **API errors**: Network and API errors are handled gracefully with descriptive error messages
- **Authentication failures**: Clear error messages for token retrieval issues

## Dependencies

- **axios**: HTTP client for API requests
- **dotenv**: Environment variable management

## Security Notes

- Never commit your `.env` file to version control
- The `.gitignore` file already excludes `.env` files
- Use the `env.example` file as a template for required environment variables

## Troubleshooting

### Common Issues:

1. **"API_KEY and API_SECRET must be set"**
   - Check that your `.env` file exists and contains the correct credentials

2. **"Error: project_uuid is required"**
   - Make sure you're providing a project UUID as an argument

3. **"Failed to get token"**
   - Verify your API credentials are correct
   - Check your network connection

4. **Empty results**
   - Verify the project UUID exists in your namespace
   - Check that the project has findings that match the filters 