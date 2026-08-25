# Finding Tag Replacer

This script removes a specified tag from findings within a project and replaces it with a new tag using the project UUID.

## Setup

### Step 1: Create .env file

Create a `.env` file in the project root with the following variables:

```
API_KEY=<your_api_key_here>
API_SECRET=<your_api_secret_here>
ENDOR_NAMESPACE=<your_namespace>
```

### Step 2: Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Run the script

```bash
python3 main.py --old-tag <old_tag> --new-tag <new_tag> --project-uuid <project_uuid> [--branch <branch_name>]
```

Examples:
```bash
python3 main.py --old-tag "old-tag" --new-tag "new-tag" --project-uuid "abc123-def456-ghi789"
python3 main.py --old-tag "dev-repo" --new-tag "prod-repo" --project-uuid "abc123-def456-ghi789"
python3 main.py --old-tag "dev-repo" --new-tag "prod-repo" --project-uuid "abc123-def456-ghi789" --branch "feature-branch"
```

## Command Line Options

- `--old-tag`: Tag to remove from findings (required)
- `--new-tag`: Tag to add to findings (required)  
- `--project-uuid`: Project UUID containing the findings to process (required)
- `--branch`: Branch context to analyze (optional, defaults to main context)

## Tag Requirements

Tags must meet the following requirements:
- **Length**: 63 characters or less
- **Characters**: Only letters (A-Z), numbers (0-9), and the following special characters: `=@_.-`
- **Examples**: `prod-repo`, `dev@v1.0`, `test_env`, `release=2024`

## What the script does

1. Takes a project UUID as command line argument
2. For the project:
   - Finds all findings that have the specified old tag
   - Removes the old tag from each finding (if it exists)
   - Adds the new tag to each finding (if it doesn't already exist)
   - Updates each finding with the modified tag list
3. Provides detailed feedback for each finding operation

## Output

The script will show progress for each finding:
- Number of findings found with the old tag
- ✅ Success messages for each finding update
- ❌ Error messages if updates fail
- Detailed feedback about tag operations (removed/added)
- Summary of total findings updated
