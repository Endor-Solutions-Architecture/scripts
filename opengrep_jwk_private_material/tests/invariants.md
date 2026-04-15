# JWK Secrets Invariants

## Detection Invariants

1. Private JWK material must be flagged when:
   - a core private JWK parameter exists (`d`, `p`, `q`, `dp`, `dq`), or
   - `kty: "oct"` with `k` exists.
2. JSON private JWK objects must be flagged regardless of package or library mapping context.
3. Per-language and agnostic-pass evaluations must both be emitted in benchmark reporting.
4. Strict-enhanced profile enforces base64url-compatible character sets for matched private-value fields.
5. Strict-enhanced profile applies minimum length floors on sensitive values (`d`, `k`, `p`, `q`, `dp`, `dq`) for defensible findings.
6. Generated corpus labels are security-truth based for the performance-critical set: (`k`, `d`, `p`, `q`, `dp`, `dq`) are expected positive across all ecosystems.
7. `qi` and `oth` are treated as tricky/extended private indicators and are excluded from strict generated-manifest pass/fail expectations.
8. Generated corpus includes performance-stress fixtures in the same manifest, and they remain strict pass/fail cases.
9. Performance-stress fixtures are emitted across all tiers and profiles so orchestration can choose target tiers without regenerating data.
10. Strict-positive generated fixtures must be schema-correct for declared key type and algorithm.
11. Strict-positive tracked private fields must satisfy declared base64url charset and exact length expectations.

## Non-Detection Invariants

1. Public-only JWK material (for example `kty` + `n` + `e` without private params) must not be flagged.
2. Random text mentioning tokens like `kty` and `d` outside JWK object shape should not be flagged.
3. Cross-language fixtures are strict TDD expectations; unsupported behavior is treated as a failing regression candidate.

## Ground Truth Contract

- `tests/ground-truth.json` is the source of truth.
- `generated/ground-truth-generated.json` is a security-truth manifest for stress/coverage testing of the performance-critical key set.
- `generated/` is the only canonical generated corpus directory.
- Primary label policy: `expected_match` is the only normative label used for pass/fail.
- A validation pass is successful when each case's `expected_match` state is satisfied.
- Any mismatch must be treated as a regression candidate and investigated.
- Label semantics prioritize secrets-detection recall over strict parsing fidelity:
  - false negatives on sensitive material are treated as the highest-severity failures,
  - false positives are accepted as a tradeoff when needed to preserve recall.
- Fixtures may include malformed or non-canonical structures to model realistic leakage patterns; these remain valid security-truth cases.
- Strict-positive fixture contract fields are normative when present (`strict_positive_schema`, `expected_kty`, `expected_alg`, `required_fields`, `sensitive_fields`, `field_length_expectations`).
- Generated corpus interpretation:
  - expected true + observed false = detector gap (must be addressed)
  - expected false + observed true = false-positive control hit
- Benchmark output contract:
  - `quality` section must include per-language and agnostic-pass metrics,
  - `performance` section must include per-language, agnostic-pass, and total two-pass runtime.
  - strict profile A/B runs should emit `profile_comparison` with explicit base/compare metrics and deltas.
