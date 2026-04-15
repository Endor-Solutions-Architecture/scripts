from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any


def _run_opengrep(config_args: list[str], target: Path) -> dict[str, Any]:
    cmd = [
        "opengrep",
    ] + config_args + [
        "--json",
        "--no-rewrite-rule-ids",
        "--no-git-ignore",
        "--x-ignore-semgrepignore-files",
        str(target),
    ]
    start = time.perf_counter()
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    duration_ms = int((time.perf_counter() - start) * 1000)

    if proc.returncode not in (0, 1):
        raise RuntimeError(
            f"opengrep failed with exit code {proc.returncode}: {proc.stderr.strip()}"
        )

    payload = json.loads(proc.stdout or "{}")
    findings = payload.get("results", [])
    counts_by_rule: dict[str, int] = {}
    for finding in findings:
        rule_id = finding.get("check_id", "unknown")
        counts_by_rule[rule_id] = counts_by_rule.get(rule_id, 0) + 1

    return {
        "duration_ms": duration_ms,
        "finding_count": len(findings),
        "counts_by_rule": counts_by_rule,
        "raw_results": findings,
    }


def _run_opengrep_with_config(config: Path, target: Path) -> dict[str, Any]:
    return _run_opengrep(["--config", str(config)], target)


def _run_opengrep_with_configs(configs: list[Path], target: Path) -> dict[str, Any]:
    args: list[str] = []
    for config in configs:
        args.extend(["--config", str(config)])
    return _run_opengrep(args, target)


def _load_ground_truth(path: Path) -> list[dict[str, Any]]:
    content = json.loads(path.read_text(encoding="utf-8"))
    return content.get("cases", [])


def _normalize_path(path_str: str) -> str:
    return path_str.replace("\\", "/")


def _validate_ground_truth(
    fixtures_root: Path, cases: list[dict[str, Any]], findings: list[dict[str, Any]]
) -> list[str]:
    observed: set[tuple[str, str]] = set()
    for finding in findings:
        rel = _normalize_path(Path(finding["path"]).relative_to(fixtures_root).as_posix())
        observed.add((rel, finding.get("check_id", "")))

    errors: list[str] = []
    for case in cases:
        key = (_normalize_path(case["path"]), case["rule_id"])
        has_match = key in observed
        if bool(case["expected_match"]) != has_match:
            errors.append(
                f'{case["id"]}: expected {case["expected_match"]}, observed {has_match} '
                f'for ({case["path"]}, {case["rule_id"]})'
            )
    return errors


def _validate_generated_manifest(
    generated_root: Path, cases: list[dict[str, Any]], findings: list[dict[str, Any]]
) -> list[str]:
    observed_by_path: dict[str, list[dict[str, Any]]] = {}
    for finding in findings:
        rel = _normalize_path(Path(finding["path"]).relative_to(generated_root).as_posix())
        observed_by_path.setdefault(rel, []).append(finding)

    errors: list[str] = []
    for case in cases:
        rel_path = _normalize_path(case["path"])
        observed = observed_by_path.get(rel_path, [])
        has_match = bool(observed)
        expected_match = bool(case["expected_match"])
        if expected_match != has_match:
            errors.append(
                f'{case["id"]}: expected_match={expected_match}, observed={has_match} at {rel_path}'
            )
            continue
        if expected_match:
            expected_line = int(case.get("expected_line", 1))
            line_hit = any(int(f["start"]["line"]) <= expected_line <= int(f["end"]["line"]) for f in observed)
            if not line_hit:
                errors.append(
                    f'{case["id"]}: expected line {expected_line} not covered by findings for {rel_path}'
                )
    return errors


_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _extract_payload_json(file_content: str) -> str | None:
    marker = "JWK_PAYLOAD:"
    if marker in file_content:
        after = file_content.split(marker, 1)[1]
        line = after.splitlines()[0].strip()
        if line:
            return line
    if file_content.startswith("blob="):
        return file_content.split("=", 1)[1].strip()
    first = file_content.find("{")
    last = file_content.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return None
    return file_content[first : last + 1]


def _validate_case_payload_contract(generated_root: Path, case: dict[str, Any]) -> list[str]:
    if not case.get("strict_positive_schema"):
        return []
    case_path = generated_root / str(case["path"])
    content = case_path.read_text(encoding="utf-8")
    payload_text = _extract_payload_json(content)
    if not payload_text:
        return [f'{case["id"]}: unable to extract payload JSON from {case["path"]}']
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        return [f'{case["id"]}: invalid payload JSON in {case["path"]}: {exc}']

    errors: list[str] = []
    expected_kty = case.get("expected_kty")
    expected_alg = case.get("expected_alg")
    if expected_kty and payload.get("kty") != expected_kty:
        errors.append(f'{case["id"]}: expected kty={expected_kty}, observed={payload.get("kty")}')
    if expected_alg and payload.get("alg") != expected_alg:
        errors.append(f'{case["id"]}: expected alg={expected_alg}, observed={payload.get("alg")}')

    for field in case.get("required_fields", []):
        if field not in payload:
            errors.append(f'{case["id"]}: missing required field {field}')

    length_expectations = case.get("field_length_expectations", {})
    for field, expected_len in length_expectations.items():
        value = payload.get(field)
        if not isinstance(value, str):
            errors.append(f'{case["id"]}: expected string field {field}')
            continue
        if len(value) != int(expected_len):
            errors.append(
                f'{case["id"]}: field {field} length={len(value)} expected={int(expected_len)}'
            )
        if not _BASE64URL_RE.fullmatch(value):
            errors.append(f'{case["id"]}: field {field} is not base64url-compatible')

    for field in case.get("sensitive_fields", []):
        value = payload.get(field)
        if not isinstance(value, str):
            errors.append(f'{case["id"]}: sensitive field {field} is not a string')
            continue
        if not _BASE64URL_RE.fullmatch(value):
            errors.append(f'{case["id"]}: sensitive field {field} is not base64url-compatible')

    return errors


def _validate_generated_manifest_contracts(
    generated_root: Path, cases: list[dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    for case in cases:
        errors.extend(_validate_case_payload_contract(generated_root, case))
    return errors


def _generated_gap_summary(
    cases: list[dict[str, Any]], findings: list[dict[str, Any]], generated_root: Path
) -> dict[str, Any]:
    observed_paths: set[str] = set()
    for finding in findings:
        rel = _normalize_path(Path(finding["path"]).relative_to(generated_root).as_posix())
        observed_paths.add(rel)

    detector_gaps: dict[str, list[str]] = {}
    false_positive_controls: dict[str, list[str]] = {}
    for case in cases:
        rel_path = _normalize_path(case["path"])
        language = rel_path.split("/", 1)[0]
        expected_match = bool(case["expected_match"])
        observed = rel_path in observed_paths
        if expected_match and not observed:
            detector_gaps.setdefault(language, []).append(case["id"])
        elif not expected_match and observed:
            false_positive_controls.setdefault(language, []).append(case["id"])

    def _counts(grouped: dict[str, list[str]]) -> dict[str, int]:
        return {lang: len(ids) for lang, ids in sorted(grouped.items())}

    return {
        "detector_gap_count": sum(len(v) for v in detector_gaps.values()),
        "detector_gaps_by_language": _counts(detector_gaps),
        "detector_gap_case_ids": {
            lang: ids for lang, ids in sorted(detector_gaps.items())
        },
        "false_positive_control_count": sum(len(v) for v in false_positive_controls.values()),
        "false_positive_controls_by_language": _counts(false_positive_controls),
        "false_positive_control_case_ids": {
            lang: ids for lang, ids in sorted(false_positive_controls.items())
        },
    }


def _metrics(expected_cases: list[dict[str, Any]], observed_paths: set[str]) -> dict[str, Any]:
    tp = fp = tn = fn = 0
    for case in expected_cases:
        path = _normalize_path(case["path"])
        expected = bool(case["expected_match"])
        observed = path in observed_paths
        if expected and observed:
            tp += 1
        elif expected and not observed:
            fn += 1
        elif not expected and observed:
            fp += 1
        else:
            tn += 1

    total = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        (2.0 * precision * recall / (precision + recall))
        if (precision + recall)
        else 0.0
    )
    accuracy = (tp + tn) / total if total else 0.0

    return {
        "total": total,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "accuracy": round(accuracy, 6),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def _paths_from_findings(generated_root: Path, findings: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for finding in findings:
        rel = _normalize_path(Path(finding["path"]).relative_to(generated_root).as_posix())
        out.add(rel)
    return out


def _run_two_pass_report(target: Path, config_dir: Path, manifest_name: str) -> dict[str, Any]:
    manifest_path = target / manifest_name
    cases = _load_ground_truth(manifest_path)

    per_language_configs: dict[str, str] = {
        "python": "python-jwk-secrets.yml",
        "javascript": "javascript-jwk-secrets.yml",
        "typescript": "typescript-jwk-secrets.yml",
        "java": "java-jwk-secrets.yml",
        "csharp": "csharp-jwk-secrets.yml",
        "go": "go-jwk-secrets.yml",
        "plaintext": "plaintext-jwk-secrets.yml",
        "json": "json-jwk-secrets.yml",
    }
    agnostic_rule_files = [
        "java-jwk-secrets.yml",
        "csharp-jwk-secrets.yml",
        "plaintext-jwk-secrets.yml",
    ]

    per_language_quality: dict[str, Any] = {}
    per_language_perf: dict[str, Any] = {}
    for language, rule_file in per_language_configs.items():
        language_target = target / language
        run = _run_opengrep_with_config(config_dir / rule_file, language_target)
        observed = _paths_from_findings(target, run["raw_results"])
        subset = [
            case for case in cases if _normalize_path(case["path"]).startswith(f"{language}/")
        ]
        per_language_quality[language] = {
            "finding_count": run["finding_count"],
            "metrics": _metrics(subset, observed),
        }
        per_language_perf[language] = {
            "duration_ms": run["duration_ms"],
        }

    agnostic_run = _run_opengrep_with_configs(
        [config_dir / name for name in agnostic_rule_files],
        target,
    )
    agnostic_observed = _paths_from_findings(target, agnostic_run["raw_results"])
    agnostic_cases = [
        case
        for case in cases
        if any(_normalize_path(case["path"]).startswith(f"{lang}/") for lang in (
            "java",
            "csharp",
            "plaintext",
        ))
    ]

    quality = {
        "manifest": str(manifest_path),
        "per_language": per_language_quality,
        "agnostic_pass": {
            "finding_count": agnostic_run["finding_count"],
            "metrics": _metrics(agnostic_cases, agnostic_observed),
        },
    }
    total_duration_ms = sum(v["duration_ms"] for v in per_language_perf.values()) + agnostic_run["duration_ms"]
    performance = {
        "per_language_duration_ms": per_language_perf,
        "agnostic_pass_duration_ms": agnostic_run["duration_ms"],
        "total_two_pass_duration_ms": total_duration_ms,
    }

    return {
        "target": str(target),
        "quality": quality,
        "performance": performance,
    }


def _profile_delta(base: dict[str, Any], compare: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "per_language": {},
        "agnostic_pass": {},
        "performance": {},
    }
    languages = sorted(base["quality"]["per_language"].keys())
    for language in languages:
        b = base["quality"]["per_language"][language]["metrics"]
        c = compare["quality"]["per_language"][language]["metrics"]
        out["per_language"][language] = {
            "recall_delta": round(c["recall"] - b["recall"], 6),
            "precision_delta": round(c["precision"] - b["precision"], 6),
            "f1_delta": round(c["f1"] - b["f1"], 6),
            "fp_delta": int(c["fp"] - b["fp"]),
            "fn_delta": int(c["fn"] - b["fn"]),
        }

    gb = base["quality"]["agnostic_pass"]["metrics"]
    gc = compare["quality"]["agnostic_pass"]["metrics"]
    out["agnostic_pass"] = {
        "recall_delta": round(gc["recall"] - gb["recall"], 6),
        "precision_delta": round(gc["precision"] - gb["precision"], 6),
        "f1_delta": round(gc["f1"] - gb["f1"], 6),
        "fp_delta": int(gc["fp"] - gb["fp"]),
        "fn_delta": int(gc["fn"] - gb["fn"]),
    }

    base_total = int(base["performance"]["total_two_pass_duration_ms"])
    cmp_total = int(compare["performance"]["total_two_pass_duration_ms"])
    out["performance"] = {
        "total_two_pass_duration_ms_delta": cmp_total - base_total,
        "total_two_pass_duration_pct_delta": round(
            ((cmp_total - base_total) / base_total) * 100 if base_total else 0.0,
            4,
        ),
    }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark JWK secrets rules.")
    parser.add_argument("--target", required=True, help="Path to scan")
    parser.add_argument(
        "--config-dir",
        default="src/jwk-secrets/rules",
        help="Rules directory for OpenGrep",
    )
    parser.add_argument(
        "--baseline-file",
        default="src/jwk-secrets/tests/baseline.json",
        help="Baseline timing and count JSON",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Write current run as baseline",
    )
    parser.add_argument(
        "--check-ground-truth",
        action="store_true",
        help="Validate findings against tests/ground-truth.json",
    )
    parser.add_argument(
        "--check-generated-ground-truth",
        action="store_true",
        help="Validate findings against generated manifest in target root",
    )
    parser.add_argument(
        "--generated-manifest-name",
        default="ground-truth-generated.json",
        help="Manifest file name under generated target root",
    )
    parser.add_argument(
        "--two-pass-report",
        action="store_true",
        help="Run per-language pass and generic pass metrics using generated manifest",
    )
    parser.add_argument(
        "--compare-config-dir",
        default="",
        help="Optional second rules directory for profile comparison in two-pass report",
    )
    args = parser.parse_args()

    target = Path(args.target)
    config_dir = Path(args.config_dir)
    baseline_file = Path(args.baseline_file)

    stats = _run_opengrep_with_config(config=config_dir, target=target)
    summary = {
        "target": str(target),
        "duration_ms": stats["duration_ms"],
        "finding_count": stats["finding_count"],
        "counts_by_rule": stats["counts_by_rule"],
    }

    print(json.dumps(summary, indent=2))

    if args.check_ground_truth:
        ground_truth_path = Path("src/jwk-secrets/tests/ground-truth.json")
        cases = _load_ground_truth(ground_truth_path)
        print("Primary label: expected_match.")
        errors = _validate_ground_truth(
            fixtures_root=Path("src/jwk-secrets/tests/fixtures"),
            cases=cases,
            findings=stats["raw_results"],
        )
        if errors:
            print("Ground truth mismatches:")
            for err in errors:
                print(f"- {err}")
            raise SystemExit(2)
        print("Ground truth validation passed.")

    if args.check_generated_ground_truth:
        manifest_path = target / args.generated_manifest_name
        cases = _load_ground_truth(manifest_path)
        print("Primary label: expected_match.")
        errors = _validate_generated_manifest(
            generated_root=target,
            cases=cases,
            findings=stats["raw_results"],
        )
        contract_errors = _validate_generated_manifest_contracts(
            generated_root=target,
            cases=cases,
        )
        gap_summary = _generated_gap_summary(
            cases=cases,
            findings=stats["raw_results"],
            generated_root=target,
        )
        print("Generated detector-gap summary:")
        print(json.dumps(gap_summary, indent=2))
        contract_summary = {
            "contract_checks": {
                "encoding_charset": "base64url",
                "length_check_mode": "exact",
                "strict_positive_schema_checks": True,
            },
            "contract_error_count": len(contract_errors),
        }
        print("Generated encoding/length contract summary:")
        print(json.dumps(contract_summary, indent=2))
        if contract_errors:
            print("Generated manifest contract mismatches:")
            for err in contract_errors:
                print(f"- {err}")
            raise SystemExit(4)
        if errors:
            print("Generated ground truth mismatches:")
            for err in errors:
                print(f"- {err}")
            raise SystemExit(3)
        print("Generated ground truth validation passed.")

    if args.two_pass_report:
        report = _run_two_pass_report(
            target=target,
            config_dir=config_dir,
            manifest_name=args.generated_manifest_name,
        )
        if args.compare_config_dir:
            compare_report = _run_two_pass_report(
                target=target,
                config_dir=Path(args.compare_config_dir),
                manifest_name=args.generated_manifest_name,
            )
            combined = {
                "target": str(target),
                "profile_comparison": {
                    "base_config_dir": str(config_dir),
                    "compare_config_dir": str(args.compare_config_dir),
                    "base": report,
                    "compare": compare_report,
                    "delta_compare_minus_base": _profile_delta(report, compare_report),
                },
            }
            print(json.dumps(combined, indent=2))
        else:
            print(json.dumps(report, indent=2))

    if args.write_baseline:
        baseline_file.parent.mkdir(parents=True, exist_ok=True)
        baseline_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Wrote baseline: {baseline_file}")
        return

    if baseline_file.exists():
        baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
        baseline_ms = int(baseline.get("duration_ms", 1))
        delta_ms = stats["duration_ms"] - baseline_ms
        pct = (delta_ms / baseline_ms) * 100 if baseline_ms else 0.0
        print(
            f"Baseline compare: current={stats['duration_ms']}ms, "
            f"baseline={baseline_ms}ms, delta={delta_ms}ms ({pct:.2f}%)"
        )


if __name__ == "__main__":
    main()
