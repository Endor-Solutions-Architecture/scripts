# Endor Labs Mega SBOM Generator

Generate a consolidated CycloneDX SBOM (Software Bill of Materials) by exporting and merging multiple SBOMs across multiple projects from the Endor Labs platform. This tool can automatically traverse sub-namespaces to find projects across your entire namespace hierarchy.

## Features

- **Multi-Project Export**: Export SBOMs for multiple projects in a single run
- **Child Namespace Traversal**: Automatically discovers and searches projects in child namespaces (up to 5 levels deep by default)
- **CycloneDX Format**: Outputs industry-standard CycloneDX JSON format
- **Component Deduplication**: Merges duplicate components across projects
- **Portfolio View**: Creates a synthetic portfolio component that links all projects
- **Namespace Distribution Report**: Shows which namespaces contained which projects

## Prerequisites

- **Python 3.7+**
- **endorctl CLI**: Installed and authenticated
  - [Install endorctl](https://docs.endorlabs.com/endorctl/install/)
  - Authenticate using `endorctl init` or via API key/token

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/your-org/mega-sbom-export.git
   cd mega-sbom-export
   ```

2. Ensure `endorctl` is installed and authenticated ([docs here for reference](https://docs.endorlabs.com/endorctl/install-and-configure/)):
   ```bash
   endorctl init
   ```

## Usage

### Basic Usage

**Step 1:** Create a text file containing the projects you want to include in your mega SBOM (one project per line). Here's an example projects.txt file:

```
https://github.com/your-org/project1.git
https://github.com/your-org/project2.git
https://dev.azure.com/your-org/project3/_git/project3
```

You can create this file manually, or use the Endor Labs API to generate it automatically:

```bash
endorctl api list -r Project -n your-namespace \
  --traverse \
  --filter 'meta.name matches "your-filter"' \
  --field-mask=meta.name \
  --list-all \
| jq -r '.list.objects[].meta.name' > projects.txt
```

**Step 2:** Run the script with your projects list from the projects.txt file:
   ```bash
   python make_mega_sbom.py \
     -n your-namespace \
     -p projects.txt \
     -o mega-sbom.json \
     --portfolio-name "My Portfolio"
   ```

### Command Line Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `-n, --namespace` | Yes | - | Parent Endor namespace (will also search child namespaces) |
| `-p, --projects-file` | Yes | - | Path to text file with project names (one per line) |
| `-o, --output` | No | `mega-sbom.cyclonedx.json` | Output SBOM file path |
| `--portfolio-name` | No | `Portfolio` | Name of the synthetic portfolio root component |
| `--max-depth` | No | `5` | Maximum depth to traverse child namespaces |
| `--no-child-namespaces` | No | `false` | Disable child namespace traversal |
| `--debug` | No | `false` | Enable debug output for namespace discovery |

### Examples

> 📁 See the [`example_files/`](example_files/) folder for sample input and output files.

**Export with child namespace traversal (default):**
```bash
python make_mega_sbom.py \
  -n my-namespace \
  -p projects.txt \
  -o mega-sbom.json \
  --portfolio-name "My Portfolio"
```

**Export with debug output to see namespace discovery:**
```bash
python make_mega_sbom.py \
  -n my-namespace \
  -p projects.txt \
  -o mega-sbom.json \
  --debug
```

**Export from single namespace only (no child traversal):**
```bash
python make_mega_sbom.py \
  -n my-namespace \
  -p projects.txt \
  -o mega-sbom.json \
  --no-child-namespaces
```

**Increase traversal depth for deep namespace hierarchies:**
```bash
python make_mega_sbom.py \
  -n my-namespace \
  -p projects.txt \
  -o mega-sbom.json \
  --max-depth 10
```

## How It Works

### Namespace Traversal

The script automatically discovers child namespaces using the Endor Labs API. For example, given this namespace hierarchy:

```
my-namespace
├── sub-namespace-1
│   └── sub-namespace-1a
│       ├── project-a
│       └── project-b
├── sub-namespace-2
│   └── sub-namespace-2a
└── sub-namespace-3
```

The script will:
1. Query `my-namespace` for direct children → finds `sub-namespace-1`, `sub-namespace-2`, `sub-namespace-3`
2. Query `my-namespace.sub-namespace-1` for children → finds `sub-namespace-1a`
3. Query `my-namespace.sub-namespace-1.sub-namespace-1a` for children → finds `project-a`, `project-b`
4. Continue until max depth or no more children

### Project Resolution

For each project in your input file:
1. Search for the project UUID in the parent namespace
2. If not found, search in each discovered child namespace
3. Export the SBOM from the namespace where the project was found

### SBOM Merging

The merged SBOM:
- **Deduplicates components** by purl+version (or name+version+type if no purl)
- **Resolves bom-ref collisions** by appending unique suffixes
- **Merges dependencies** from all source SBOMs
- **Creates a portfolio root** that depends on each project's root component

## Output Files

| File | Description |
|------|-------------|
| `<output>.json` | The merged CycloneDX SBOM |
| `<output-prefix>-failed_projects.txt` | List of projects that failed to export (only created if there are failures) |

For example, if you use `-o mega-sbom.json`, failures will be written to `mega-sbom-failed_projects.txt`.

See [`example_files/mega-sbom-example.json`](example_files/mega-sbom-example.json) for a sample output.

## Sample Output

```
Discovering child namespaces under 'my-namespace'...
  Found child namespace: my-namespace.sub-namespace-1 (depth 1)
  Found child namespace: my-namespace.sub-namespace-2 (depth 1)
  Found child namespace: my-namespace.sub-namespace-1.sub-namespace-1a (depth 2)
Found 4 namespace(s):
    - my-namespace
    - my-namespace.sub-namespace-1
    - my-namespace.sub-namespace-2
    - my-namespace.sub-namespace-1.sub-namespace-1a
Loaded 10 project(s) from projects.txt
Exporting CycloneDX SBOMs for 10 projects...
  [1/10] https://github.com/my-org/project1.git
  [2/10] https://dev.azure.com/my-org/project2/_git/project2
    (found in child namespace: my-namespace.sub-namespace-1.sub-namespace-1a)
  ...

Namespace distribution:
  my-namespace: 6 project(s)
  my-namespace.sub-namespace-1.sub-namespace-1a: 4 project(s)

Merging SBOMs...
Done. Wrote mega-sbom.json
```

## Troubleshooting

### "ERROR unknown" or API failures

- Ensure `endorctl` is properly authenticated: `endorctl init`
- Check that you have access to the namespace and its children
- Try running with `--debug` to see detailed API responses

### Projects not found in child namespaces

- Verify the project exists in the Endor Labs UI
- Check the exact project name/URL matches what's in Endor Labs
- Use `--debug` to see which namespaces are being searched

### Permission errors on child namespaces

- Ensure your API key/token has access to the parent namespace
- Child namespace access is inherited from the parent
