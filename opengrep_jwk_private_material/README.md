# OpenGrep rules: hardcoded private JWK material

OpenGrep / Semgrep rules that flag **JSON Web Key (JWK)**-shaped literals in source or config where **private key material** appears (for example RSA/EC/OKP private parameters or symmetric `oct` key material). They are useful for secret detection and SAST workflows; they do **not** assert that a key is cryptographically valid.

## Scope

- **Languages / formats:** Python, JavaScript, TypeScript, Java, C#, Go, JSON, and generic text/config files (see each file’s `paths.include`).
- **References:** [RFC 7517](https://datatracker.ietf.org/doc/html/rfc7517), [RFC 7518](https://datatracker.ietf.org/doc/html/rfc7518).

| Rule file | Focus |
| --- | --- |
| `rules/python-jwk-secrets.yml` | Python dict literals |
| `rules/javascript-jwk-secrets.yml` | JavaScript object literals |
| `rules/typescript-jwk-secrets.yml` | TypeScript object literals |
| `rules/java-jwk-secrets.yml` | Java string / JSON-like fragments |
| `rules/csharp-jwk-secrets.yml` | C# string / JSON-like fragments |
| `rules/go-jwk-secrets.yml` | Go map literals and regex fallbacks |
| `rules/json-jwk-secrets.yml` | JSON documents |
| `rules/plaintext-jwk-secrets.yml` | Plaintext and config extensions |

## Validate locally

Use [OpenGrep](https://github.com/opengrep/opengrep) or [Semgrep](https://semgrep.dev/) with the same rule YAML:

```bash
opengrep scan --config rules/python-jwk-secrets.yml /path/to/repo
# or
semgrep scan --config rules/python-jwk-secrets.yml /path/to/repo
```

To validate rule YAML without scanning:

```bash
opengrep scan --config rules/python-jwk-secrets.yml --validate
```

## Import into Endor Labs

Rules in this folder include metadata accepted by the Endor Labs Semgrep rule API (`category`, `cwe`, `endor-*`, `rule-origin-note`, etc.). Import using your preferred method:

- **Python SDK:** use [`sast_rule_manager.py`](https://github.com/Endor-Solutions-Architecture/endorlabs-sdk/blob/main/.cursor/skills/custom-sast-rules/scripts/sast_rule_manager.py) from the [endorlabs-sdk](https://github.com/Endor-Solutions-Architecture/endorlabs-sdk) repository (`.cursor/skills/custom-sast-rules/scripts/`), with `--rules-dir` set to this `rules/` directory and `--namespace` set to your tenant namespace.
- **Credentials:** set `ENDOR_API_CREDENTIALS_KEY`, `ENDOR_API_CREDENTIALS_SECRET`, and target namespace per your environment; never commit secrets.

After import, run a SAST scan (for example `endorctl scan --sast`) on a repository to verify findings.

## Canonical copy

This directory is the **canonical** location for these rules under this repository. Rule YAML `metadata.description` fields reference this path for traceability.
