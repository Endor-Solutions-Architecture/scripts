# JWK Secrets (OpenGrep)

Specification for this directory: **rule packs**, **generated test corpus**, **benchmark harness**, and **ground-truth labeling** for detecting private JWK-shaped material in source and text.

---

## Rule packs

| Path | Definition |
| --- | --- |
| `rules` | Default profile: recall-oriented patterns for private JWK fields and stringified forms. |
| `rules-strict` | Strict profile: extra charset/length constraints on matched values. |
| `rules-strict-baseline` | Frozen snapshot of strict rules for A/B comparison against `rules-strict`. |

Detection scope (all profiles): private JWK parameters such as `d`, CRT fields `p`, `q`, `dp`, `dq` where applicable, and `k` for `kty: "oct"`. Object literals and stringified JSON (including escaped quotes in strings) are in scope. Rules do **not** assert cryptographic validity of keys—only presence of sensitive-shaped material.

---

## Paths and languages

Rules are organized per language plus JSON and a shared text/config rule. `paths.include` in each YAML lists file extensions; summarized:

| Bucket | Extensions |
| --- | --- |
| Python | `.py`, `.pyw`, `.pyi` |
| JavaScript | `.js`, `.mjs`, `.cjs`, `.jsx` |
| TypeScript | `.ts`, `.tsx`, `.mts`, `.cts` |
| Java | `.java` |
| C# | `.cs`, `.csx` |
| Go | `.go` |
| JSON | `.json` |
| Text / config | `.txt`, `.conf`, `.ini`, `.env`, `.yaml`, `.yml`, `.toml`, `.cfg`, `.config`, `.properties`, `.tfvars`, `.tfvars.json` |

---

## Tests and ground truth

- **Manifest:** `generated/ground-truth-generated.json` (generated; primary label field `expected_match`).
- **Invariants and acceptance criteria:** `tests/invariants.md`.
- **Corpus generator:** `scripts/generate_pathological_corpus.py` writes under `generated/` (gitignored by default).

```bash
python scripts/generate_pathological_corpus.py --output generated --files-per-language 50
```

```bash
python scripts/generate_pathological_corpus.py --output generated --files-per-language 50 --no-include-stress-fixtures
```

---

## Benchmarks

**Script:** `scripts/benchmark_rules.py`.

**Reference corpus** for the table below: `generated` — 424 labeled cases, 424 files, ~2014 lines; labels from `ground-truth-generated.json`. Figures are for comparing rule **profiles** on that corpus and machine; they are not a general performance or accuracy claim outside this test setup.

| Profile | One full scan (ms) | Findings | Pass 2 P | Pass 2 R | Pass 2 F1 | Benchmark total (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `rules` | 8661 | 394 | 1.0000 | 0.9091 | 0.9524 | 22982 |
| `rules-strict-baseline` | 8701 | 332 | 1.0000 | 0.3636 | 0.5333 | 22413 |
| `rules-strict` | 9777 | 332 | 1.0000 | 0.3636 | 0.5333 | 22764 |

**Column definitions**

- **One full scan** — one OpenGrep invocation over the corpus with the full rule set for that profile.
- **Pass 2 P/R/F1** — metrics for the benchmark’s embedded-text step only (Java, C#, plaintext rule files). Per-language runs are reported separately in JSON as `quality.per_language`. This step is stored as `quality.agnostic_pass`.
- **Benchmark total** — `benchmark_rules.py --two-pass-report`: sum of per-language timed segments plus the embedded-text segment.

```bash
python scripts/benchmark_rules.py --target generated --config-dir rules --two-pass-report
python scripts/benchmark_rules.py --target generated --config-dir rules-strict-baseline --two-pass-report
python scripts/benchmark_rules.py --target generated --config-dir rules-strict --two-pass-report
```

```bash
python scripts/benchmark_rules.py --target generated --config-dir rules --check-generated-ground-truth --two-pass-report
```

---

## OpenGrep invocation (reference)

Example flags used in benchmark runs so scans are comparable and paths are not skipped via ignore files:

```bash
opengrep scan --config rules --json --no-git-ignore --x-ignore-semgrepignore-files <path>
```

Strict profile: substitute `rules-strict` for `--config`.

---

## Endor Labs (any customer tenant)

Compared to the research layout elsewhere, the **only** intentional difference in this published copy is that rule `metadata` uses fields accepted by the Endor Labs Semgrep rule API (`category`, `cwe`, `endor-category`, `endor-tags`, `rule-origin-note`, etc.), so you can register these packs in **any** tenant using normal API credentials.

- **Import:** use the [endorlabs-sdk](https://github.com/Endor-Solutions-Architecture/endorlabs-sdk) helper [`sast_rule_manager.py`](https://github.com/Endor-Solutions-Architecture/endorlabs-sdk/blob/main/.cursor/skills/custom-sast-rules/scripts/sast_rule_manager.py):  
  `python sast_rule_manager.py --namespace <tenant.namespace> import --rules-dir <profile-dir> [--force]`  
  with `ENDOR_API_CREDENTIALS_KEY`, `ENDOR_API_CREDENTIALS_SECRET`, and your target namespace in the environment.

- **Profiles:** each rule file uses the same `id` across `rules/`, `rules-strict/`, and `rules-strict-baseline/`. Import **one profile directory at a time** (or use distinct namespaces) so updates do not overwrite another profile’s YAML for the same rule name.

---

## Labeling contract

- Manifest labels are **security-truth** oriented (recall-first for sensitive-shaped material), not full key validation.
- Strict profiles add heuristics (length/charset); they do **not** verify RSA/EC relationships (e.g. `p*q=n`).
