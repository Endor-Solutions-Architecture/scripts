# Endor VEX Enrichment Tool

This tool enriches VEX (Vulnerability Exploitability eXchange) documents exported from Endor Labs with additional vulnerability analysis information based on exception policies. It automatically incorporates policy-based exceptions and their associated metadata into the VEX document, making it more informative and compliant with industry standards.

## Features

Core Features:
- Authenticates with the Endor Labs API
- Exports VEX documents for packages
- Enriches VEX documents with exception policy information according to ECMA-424 including:
  - Analysis state
  - Justification tags
  - Response actions
  - Policy descriptions
  - Timestamps

Operating Modes:
1. Namespace Mode:
   - Automatically discovers all packages in a namespace (excluding GitHub Actions)
   - Retrieves findings with exceptions for all discovered packages
   - Generates a comprehensive VEX document for the entire namespace

2. Targeted Mode:
   - Processes specific packages using provided UUIDs
   - Retrieves findings with exceptions for listed packages only
   - Generates a focused VEX document for selected packages

## Prerequisites

- Python 3.6 or higher
- Access to Endor Labs API with credentials (API key and secret)

## Installation

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the project root with your Endor Labs credentials (or supply as environment variables):
```
API_KEY=your_api_key
API_SECRET=your_api_secret
ENDOR_NAMESPACE=your_namespace (optional - can also be provided via a command line argument)
```

## Usage

The tool can be run in two different modes:

### 1. Namespace-only Mode
```bash
python endor_vex.py --namespace your_namespace
```
In this mode, the tool will:
- Scan your entire namespace
- Automatically discover and include ALL packages in the namespace (excluding GitHub Actions)
- Process findings and exceptions for every package found
- Generate a comprehensive VEX document for your entire namespace

This is useful when you want to:
- Get a complete overview of all packages
- Don't want to manually specify package UUIDs
- Need to process your entire namespace in one go

### 2. Targeted Package Mode
```bash
python endor_vex.py --package-uuids uuid1,uuid2,uuid3
```
In this mode, the tool will:
- Only process the specific packages you list
- Focus the analysis on just those packages
- Generate a VEX document for only the specified packages
  ```bash
  python endor_vex.py --namespace your_namespace --package-uuids uuid1,uuid2,uuid3
  ```

This is useful when you want to:
- Focus on specific packages of interest
- Generate targeted VEX documents for particular packages
- Process a subset of packages from your namespace

The script will then:
1. Authenticate with the Endor Labs API
2. Either fetch all packages (namespace mode) or use provided package UUIDs (targeted mode)
3. Retrieve findings with exceptions
4. Export and enrich a VEX document
5. Save the enriched VEX document to the `vex_exports` directory

## Output

The tool generates a JSON file in the `vex_exports` directory with the naming format:
```
vex_export_YYYYMMDD_HHMMSS.json
```

The output follows the CycloneDX VEX JSON format, enriched with analysis information from your Endor Labs exception policies.

## Error Handling

The script includes comprehensive error handling for:
- Missing environment variables
- API authentication failures
- Request timeouts
- Invalid responses
- File system operations

If any error occurs, the script will exit with a status code of 1 and display an appropriate error message.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT