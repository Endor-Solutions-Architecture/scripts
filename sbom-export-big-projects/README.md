# Batch SBOM Exporter for Endor Labs

A Python script that exports SBOMs from the Endor Labs REST API using the same batching strategy as `endorctl sbom export`. Splits package-version UUIDs into batches, calls the export API for each batch concurrently, and merges the results client-side. This avoids the timeouts you hit on large projects with many packages and dependencies.

## Requirements

- Python 3.10+
- An Endor Labs API token

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
source .venv/bin/activate

python batch_sbom_export.py \
  --namespace my-namespace \
  --token "$ENDOR_TOKEN" \
  --project-uuid 6123abcdef... \
  --app-name my-application
```

### Write to file

```bash
python batch_sbom_export.py \
  --namespace my-namespace \
  --token "$ENDOR_TOKEN" \
  --project-uuid 6123abcdef... \
  --app-name my-application \
  --output sbom.json
```

### SPDX format

```bash
python batch_sbom_export.py \
  --namespace my-namespace \
  --token "$ENDOR_TOKEN" \
  --project-uuid 6123abcdef... \
  --app-name my-application \
  --sbom-kind spdx
```

### Very large projects

Give the API a longer budget per request and raise concurrency:

```bash
python batch_sbom_export.py \
  --namespace my-namespace \
  --token "$ENDOR_TOKEN" \
  --project-uuid 6123abcdef... \
  --app-name my-application \
  --timeout 300 \
  --workers 8 \
  --output sbom.json
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--namespace` | *required* | Endor Labs namespace |
| `--token` | *required* | API bearer token |
| `--project-uuid` | *required* | UUID of the project to export |
| `--app-name` | *required* | Application name for the SBOM |
| `--sbom-kind` | `cyclonedx` | SBOM standard (`cyclonedx` or `spdx`) |
| `--output-format` | `json` | Output encoding (`json`, `xml`, `tag-value`) |
| `--component-type` | `application` | Component type (`application` or `library`) |
| `--batch-size` | `25` | Package-version UUIDs per `sbom-export` call |
| `--page-size` | `500` | Package versions per listing request |
| `--timeout` | `120` | Seconds the API may spend per request, sent as the `Request-Timeout` header |
| `--workers` | `8` | Concurrent `sbom-export` requests (listing is always sequential) |
| `--output`, `-o` | stdout | Output file path |
| `--verbose`, `-v` | off | Enable debug logging |

## How it works

1. **List package versions** via `GET /v1/namespaces/{ns}/package-versions`, walking pages with a `uuid > <last seen>` cursor. This is sequential and takes roughly a second per page. **No sort parameter is sent** — see the note below.
2. **Split** the UUIDs into batches (`--batch-size`).
3. **Export** batches via `POST /v1/namespaces/{ns}/sbom-export`, up to `--workers` at a time. The server handles license lookups, dependency graph traversal, and SBOM generation for each batch. This phase dominates total runtime, which is why it is the part that runs concurrently.
4. **Merge** all batch responses into a single SBOM by deduplicating components (by PURL) and merging dependency entries (by ref).
5. **Output** the merged SBOM as JSON to stdout or a file.

## Never add an explicit uuid sort

Measured on a large monorepo project with over ten thousand package versions:

| Request | Time |
|---------|------|
| `page_size=100`, no sort | 0.4s |
| `page_size=100`, `sort.path=uuid` | **138.8s** |
| `page_size=5`, `sort.path=uuid` | **147.4s** |

Adding `list_parameters.sort.path=uuid` is a 200-350x regression. It is unnecessary because the endpoint **already returns rows in ascending uuid order** — verified at shallow, middle and deep offsets at page sizes 100 and 500.

Deep offsets are also *not* expensive on this API (a page near the end of a five-figure result set took 0.6s versus 0.4s at the start), so there is nothing to gain from fetching listing pages concurrently. Listing is sequential on purpose.

Because keyset paging relies on that natural ordering, the script checks each page is ascending and logs a loud warning if it ever is not, since advancing the cursor past a page maximum would otherwise skip rows.

## Timeouts and retries

The Endor API allows each request **20 seconds by default**. A typical listing page takes ~0.4s, so a timeout means transient API slowness rather than an expensive query. `--timeout` raises the budget via the `Request-Timeout` header, which gives a slow request room to finish instead of being cut off at 20s. The client always waits 30 seconds longer than the server so it never gives up before the real response or error arrives.

Two distinct failures look similar here. Exceeding the `Request-Timeout` budget returns **408**, while an upstream gateway giving up returns **504**. Both are retried identically. The header value must be a bare integer number of seconds: `Request-Timeout: 120` is honored, while `120s` is rejected with a 400.

Failed requests retry with exponential backoff (2s, 4s, 8s, 16s). For exports, a batch that still fails is halved and each half retried, so a batch too expensive for the server degrades into smaller units. A single package version that still cannot be exported **aborts the run** rather than emitting an SBOM that is silently missing packages.

## Expected runtime

For a project with `N` package versions:

| Phase | Requests | Notes |
|-------|----------|-------|
| Listing | `ceil(N / page-size)` pages, plus one empty page to terminate and one count | Sequential, roughly a second per page |
| Export | `ceil(N / batch-size)` batches, `--workers` at a time | Dominates total runtime |

At the defaults (`--page-size 500`, `--batch-size 25`, `--workers 8`), a project with ten thousand package versions lists in well under a minute and exports in a few minutes.
