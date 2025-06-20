# Dismiss Secrets by Location

A Python script to automatically dismiss secrets in Endor Labs based on a list of specific locations.

## Overview

This script connects to the Endor Labs API to:
- Fetch secrets findings from a specified namespace
- Filter secrets based on locations from a provided file
- Dismiss matching secrets in Endor Labs
- Log all dismissed secrets to a CSV file for audit purposes

## Prerequisites

- Python 3.6 or higher
- Access to Endor Labs API
- Valid Endor Labs authentication credentials

## Installation

1. Clone or download this repository
2. Install required Python packages:
```bash
pip install requests python-dotenv
```

## Configuration

### Authentication

The script supports two authentication methods:

#### Option 1: Direct Token
Set the `ENDOR_TOKEN` environment variable:
```bash
export ENDOR_TOKEN="your-endor-token-here"
```

#### Option 2: API Credentials
Set both API credentials:
```bash
export ENDOR_API_CREDENTIALS_KEY="your-api-key"
export ENDOR_API_CREDENTIALS_SECRET="your-api-secret"
```

### Environment File (Optional)
Create a `.env` file in the script directory:
```
ENDOR_TOKEN=your-endor-token-here
# OR
ENDOR_API_CREDENTIALS_KEY=your-api-key
ENDOR_API_CREDENTIALS_SECRET=your-api-secret
```

## Usage

### Basic Syntax
```bash
python main.py --namespace <namespace> --locations-file <path-to-locations-file> [options]
```

### Required Arguments
- `--namespace`: Endor Labs namespace to process
- `--locations-file`: Path to file containing locations to dismiss (one per line)

### Optional Arguments
- `--project-uuid`: Filter secrets to a specific project UUID
- `--debug`: Enable debug output for troubleshooting
- `--no-dry-run`: Actually dismiss secrets (default is dry run mode)

### Examples

#### Dry Run (Default - Safe Mode)
```bash
python main.py --namespace my-company --locations-file locations.txt
```

#### Actually Dismiss Secrets
```bash
python main.py --namespace my-company --locations-file locations.txt --no-dry-run
```

#### Debug Mode with Specific Project
```bash
python main.py --namespace my-company --locations-file locations.txt --project-uuid 12345-abcde --debug
```

## Locations File Format

Create a text file with one location per line in the following format. The script will match secrets whose locations contain any of these strings:

```
https://github.com/myorg/myapp/blob/main/out.json#L17396
https://github.com/myorg/myapp2/blob/main/out2.json#L28387
```

## Output

### Console Output
- **Dry Run Mode**: Shows what would be dismissed with prefix `Dry run - would have dismissed secret:`
- **Live Mode**: Shows actual dismissals with prefix `Dismissing secret:`
- Summary of processed vs skipped secrets

### Log File
The script creates a CSV log file: `dismiss_secrets_by_location.dismissed.<timestamp>.log`

CSV Format:
```csv
"Namespace","Secret UUID","Description","Matched Location"
"my-namespace","uuid-123","API Key found","https://github.com/myorg/repo1/blob/main/"
```

## How It Works

1. **Authentication**: Authenticates with Endor Labs API using provided credentials
2. **Fetch Secrets**: Retrieves all secrets findings from the specified namespace
3. **Load Locations**: Reads the locations file into memory
4. **Filter & Match**: For each secret:
   - Extracts secret locations from `spec.finding_metadata.source_policy_info.results`
   - Checks if any secret location contains any location from the file
   - If match found, set finding `spec.dismiss=true` and add `FINDING_TAGS_EXCEPTION` to `spec.finding_tags`
5. **Dismiss**: In non-dry-run mode, calls Endor Labs API to dismiss matching secrets
6. **Log**: Records all dismissed secrets to CSV file

## API Details

The script uses the following Endor Labs API endpoints:
- `GET /v1/namespaces/{namespace}/findings` - Fetch secrets
- `PATCH /v1/namespaces/{namespace}/findings` - Dismiss secrets

## Safety Features

- **Dry Run by Default**: Script runs in safe mode unless `--no-dry-run` is specified
- **Detailed Logging**: All actions are logged with timestamps
- **Error Handling**: Continues processing even if individual dismissals fail
- **Pagination Support**: Handles large result sets automatically

## Troubleshooting

### Common Issues

**Authentication Failed**
```
Error: Either ENDOR_TOKEN or both ENDOR_API_CREDENTIALS_KEY and ENDOR_API_CREDENTIALS_SECRET must be set
```
- Verify your environment variables are set correctly
- Check that your credentials are valid and have necessary permissions

**No Secrets Found**
```
No secrets found or error occurred
```
- Verify the namespace exists and you have access
- Try with `--debug` flag to see API responses
- Check if there are actually secrets in the specified namespace

**Locations File Error**
```
Error loading locations from file.txt: [Errno 2] No such file or directory
```
- Verify the file path is correct
- Ensure the file exists and is readable

### Debug Mode
Use `--debug` flag to see:
- API request/response details
- Pagination information
- Location matching details
- Detailed error messages

## Security Considerations

- Store credentials securely (use environment variables or `.env` file)
- The `.env` file should not be committed to version control
- Review the locations file carefully before running
- Always test with dry run mode first
- Keep log files secure as they contain sensitive information

## License

This script is provided as-is for use with Endor Labs API integration. 
