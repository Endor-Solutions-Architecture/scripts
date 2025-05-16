# GitHub Topic to Endor Labs Project Tag Synchronization

This script synchronizes GitHub repository topics with Endor Labs project tags. It fetches topics from all repositories in a GitHub organization and updates the corresponding project tags in Endor Labs.

## Prerequisites

- Python 3.6 or higher
- GitHub Personal Access Token with `read:org` and `repo` scopes
- Endor Labs API credentials (API Key and Secret)
- Endor Labs namespace access

## Installation

1. Clone this repository and cd into `sync_project_tags_with_github_topics`
2. Install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the project root with your credentials:
   ```
   GITHUB_TOKEN=your_github_token_here
   GITHUB_ORG=your_organization_name
   API_KEY=your_endor_api
   API_SECRET=your_endor_secret
   ENDOR_NAMESPACE=your_endor_namespace (Should be specific namespace. Example: root, root.child, root.child1.child2, etc)
   ```

## Usage

Simply run the script:
```bash
python sync_tags.py
```

The script will:
1. Fetch all repositories and their topics from the specified GitHub organization
2. Find corresponding projects in Endor Labs
3. Update the Endor Labs project tags to include both existing tags and GitHub topics

## Output

The script displays a detailed table showing:
- Repository URL
- Existing Endor Labs tags
- New tags from GitHub
- Combined tags
- Update status

Example output:
```
Step 1: Fetching GitHub repositories with topics...
Found X repositories with topics

Step 2 & 3: Processing repositories in Endor Labs...
------------------------------------------------------------------------------------------------------------------------
Repository URL                              | Existing Tags        | New Tags            | Combined Tags        | Status
------------------------------------------------------------------------------------------------------------------------
https://github.com/org/repo1                | tag1, tag2          | github-topic1       | tag1, tag2, github-topic1 | Updated
https://github.com/org/repo2                | N/A                 | topic1, topic2      | topic1, topic2       | Skipped
------------------------------------------------------------------------------------------------------------------------
```

## Error Handling

The script includes comprehensive error handling:
- Validates all required environment variables
- Checks GitHub organization access
- Handles API rate limits
- Provides detailed error messages for API failures
- Gracefully handles missing repositories in Endor Labs

## Security

- Never commit your `.env` file
- Use tokens with minimal required permissions
- Keep your dependencies updated
- API credentials are stored securely in environment variables

## What's Next

- Currently the script works on specific namespaces, modify this to work from parent namespace and traverse through all namespaces
