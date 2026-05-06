# scan-artifact-no-git

Scan model artifacts (`.tar.gz` or folders) for dependency vulnerabilities using [Endor Labs](https://www.endorlabs.com/) — even when the artifact isn't in a git repository.

This is designed for environments like **Databricks** where ML models are packaged as archives containing a `requirements.txt` manifest. The script creates a synthetic git repo around the artifact so `endorctl` can perform SCA scanning.

## How it works

1. Ensures `git` and `endorctl` are installed (auto-installs if missing)
2. Extracts the artifact (if `.tar.gz`) into a temp directory
3. Removes any pre-existing `.git` directory from the artifact
4. Initializes a synthetic git repo with a remote origin that becomes the project name in the Endor Labs portal
5. Runs `endorctl scan`
6. Returns the scan exit code (`0` = passed, non-zero = policy violations found)
7. Cleans up the temp directory

## Prerequisites

The script auto-installs these if they're not on PATH:

- **git** — via `apt-get`, `yum`, `apk`, or `brew`
- **endorctl** — downloaded from the Endor Labs API

## Usage

### Environment variables (recommended)

```bash
export ENDOR_NAMESPACE=my-namespace
export ENDOR_API_KEY=my-client-id
export ENDOR_API_SECRET=my-client-secret

./scan.sh /path/to/model.tar.gz
```

### CLI arguments

```bash
./scan.sh /path/to/model.tar.gz \
  --namespace my-namespace \
  --api-key my-client-id \
  --api-secret my-client-secret
```

### Scanning a folder

```bash
./scan.sh /path/to/model-folder --namespace my-namespace --api-key my-key --api-secret my-secret
```

### All options

| Option | Env variable | Description |
|---|---|---|
| `--namespace` | `ENDOR_NAMESPACE` | Endor Labs namespace |
| `--api-key` | `ENDOR_API_KEY` | Endor Labs API key (client ID) |
| `--api-secret` | `ENDOR_API_SECRET` | Endor Labs API secret |
| `--project-name` | — | Override project name (default: derived from artifact filename) |
| `--github-org` | `ENDOR_GITHUB_ORG` | GitHub org for synthetic remote (default: `example-org`) |

## GitHub Actions

The included workflow (`.github/workflows/scan.yml`) runs `scan.sh` against the sample artifact on every push to `main`.

### Required secrets

Configure these in your GitHub repo settings under **Settings > Secrets and variables > Actions**:

- `ENDOR_NAMESPACE`
- `ENDOR_API_KEY`
- `ENDOR_API_SECRET`

### Optional variables

- `ENDOR_GITHUB_ORG` — set under **Settings > Secrets and variables > Actions > Variables**

## Sample artifact

`sample/model.tar.gz` contains a mock ML model with a `requirements.txt` for testing the workflow.

## Gating model registration

Use the exit code to gate registration in Unity Catalog or similar:

```bash
./scan.sh /path/to/model.tar.gz
if [ $? -eq 0 ]; then
  echo "Scan passed — safe to register model"
  # register in Unity Catalog
else
  echo "Scan failed — blocking model registration"
  exit 1
fi
```
