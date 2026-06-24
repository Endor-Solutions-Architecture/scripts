# Check Dependency Path Finding

Check whether a finding's **dependency path** passes through a given dependency
(e.g. `@forge/cli`), and print the path.

The full dependency path isn't a field on the Finding, so the script reads it
from the project's resolved dependency graph (on the root `PackageVersion`):
it fetches the finding, gets the graph, and checks if the finding's vulnerable
package is a descendant of your dependency.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
export ENDOR_TOKEN=...
```

Using `endorctl` locally? Mint a token:

```bash
export ENDOR_TOKEN=$(endorctl auth --print-access-token | head -n1)
```

## Usage

```bash
python3 main.py --namespace <ns> --finding-uuid <uuid> --dependency @forge/cli
```

Match an exact version with `--exact`:

```bash
python3 main.py --namespace <ns> --finding-uuid <uuid> --dependency "lodash@4.17.21" --exact
```

## Options

| Flag | Description |
| --- | --- |
| `--namespace` | Namespace the finding is in (required). |
| `--finding-uuid` | Finding to inspect (required). |
| `--dependency` | Dependency to find in the path, e.g. `@forge/cli` (required). |
| `--exact` | Match `name@version` exactly instead of by name. |

Exit codes: `0` path passes through the dependency, `1` it does not, `2` error.

## Example

```
Finding   : 690a10956c2c6b1d67125ae9
            GHSA-29mw-wpgm-hmr9: Prototype pollution in lodash
Severity  : CRITICAL
Vulnerable: lodash@4.17.21
Project   : my-app@1.0.0
Dependency: @forge/cli (by name)

YES: the finding's dependency path passes through '@forge/cli'.

Example path:
    my-app@1.0.0
 -> some-direct-dep@1.0.1
 -> @forge/cli@12.13.1
 -> lodash@4.17.21
```
