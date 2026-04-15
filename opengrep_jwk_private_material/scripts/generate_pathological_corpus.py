from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path
from typing import TypedDict


LANG_EXT = {
    "python": "py",
    "javascript": "js",
    "typescript": "ts",
    "java": "java",
    "csharp": "cs",
    "go": "go",
    "plaintext": "txt",
    "json": "json",
}


class VariantSpec(TypedDict):
    name: str
    sensitive: bool
    payload_kind: str
    expected_token: str
    risk_reason: str
    key_type: str
    alg: str
    required_fields: list[str]
    sensitive_fields: list[str]
    field_lengths: dict[str, int]


class StressTierSpec(TypedDict):
    tier: str
    decoy_count: int
    max_depth: int
    filler_width: int


class StressProfileSpec(TypedDict):
    profile: str
    expected_match: bool
    risk_reason: str
    expected_token: str


STRESS_TIERS: list[StressTierSpec] = [
    {
        "tier": "tier_token_saturation",
        "decoy_count": 120,
        "max_depth": 10,
        "filler_width": 64,
    },
    {
        "tier": "tier_structural_labyrinth",
        "decoy_count": 480,
        "max_depth": 24,
        "filler_width": 128,
    },
    {
        "tier": "tier_pathological_exhaustion",
        "decoy_count": 1500,
        "max_depth": 48,
        "filler_width": 192,
    },
]

STRESS_PROFILES: list[StressProfileSpec] = [
    {
        "profile": "stress_nearmiss_dense",
        "expected_match": False,
        "risk_reason": "performance_nearmiss_density",
        "expected_token": '"kty":"RSA"',
    },
    {
        "profile": "stress_nested_maze",
        "expected_match": False,
        "risk_reason": "performance_deep_nesting_nearmiss",
        "expected_token": '"kty":"RSA"',
    },
    {
        "profile": "stress_late_true_positive",
        "expected_match": True,
        "risk_reason": "performance_late_positive_tail_match",
        "expected_token": '"d":',
    },
]


def _rand_b64url(length: int = 48) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    return "".join(random.choice(alphabet) for _ in range(length))


def _jwk_rsa_private_json(d_len: int = 64) -> str:
    return (
        '{'
        f'"kty":"RSA","kid":"{_rand_b64url(12)}","alg":"RS256",'
        f'"n":"{_rand_b64url()}",'
        '"e":"AQAB",'
        f'"d":"{_rand_b64url(d_len)}"'
        '}'
    )


def _jwk_ec_private_json(d_len: int = 64) -> str:
    return (
        '{'
        f'"kty":"EC","kid":"{_rand_b64url(12)}","alg":"ES256","crv":"P-256",'
        f'"x":"{_rand_b64url(43)}","y":"{_rand_b64url(43)}",'
        f'"d":"{_rand_b64url(d_len)}"'
        '}'
    )


def _jwk_rsa_public_json() -> str:
    return (
        '{'
        f'"kty":"RSA","kid":"{_rand_b64url(12)}","alg":"RS256",'
        f'"n":"{_rand_b64url()}",'
        '"e":"AQAB"'
        '}'
    )


def _jwk_oct_json(include_k: bool, k_len: int = 64) -> str:
    if include_k:
        return (
            '{'
            f'"kty":"oct","kid":"{_rand_b64url(12)}","alg":"HS256",'
            f'"k":"{_rand_b64url(k_len)}"'
            '}'
        )
    return '{"kty":"oct","kid":"missing-k","alg":"HS256"}'


def _jwk_rsa_private_crt_json() -> str:
    return (
        '{'
        f'"kty":"RSA","kid":"{_rand_b64url(12)}","alg":"RS256",'
        f'"n":"{_rand_b64url()}","e":"AQAB",'
        f'"p":"{_rand_b64url()}","q":"{_rand_b64url()}",'
        f'"dp":"{_rand_b64url()}","dq":"{_rand_b64url()}"'
        '}'
    )


def _build_variant_specs() -> tuple[list[VariantSpec], list[VariantSpec]]:
    sensitive: list[VariantSpec] = [
        {
            "name": "tp_sensitive_rsa_d",
            "sensitive": True,
            "payload_kind": "rsa_d",
            "expected_token": '"d":',
            "risk_reason": "rsa_private_exponent_d",
            "key_type": "RSA",
            "alg": "RS256",
            "required_fields": ["kty", "alg", "n", "e", "d"],
            "sensitive_fields": ["d"],
            "field_lengths": {"d": 64, "n": 48},
        },
        {
            "name": "tp_sensitive_ec_d",
            "sensitive": True,
            "payload_kind": "ec_d",
            "expected_token": '"d":',
            "risk_reason": "ec_private_scalar_d",
            "key_type": "EC",
            "alg": "ES256",
            "required_fields": ["kty", "alg", "crv", "x", "y", "d"],
            "sensitive_fields": ["d"],
            "field_lengths": {"d": 64, "x": 43, "y": 43},
        },
        {
            "name": "tp_sensitive_oct_k",
            "sensitive": True,
            "payload_kind": "oct_k",
            "expected_token": '"k":',
            "risk_reason": "symmetric_secret_k",
            "key_type": "oct",
            "alg": "HS256",
            "required_fields": ["kty", "alg", "k"],
            "sensitive_fields": ["k"],
            "field_lengths": {"k": 64},
        },
        {
            "name": "tp_sensitive_rsa_crt",
            "sensitive": True,
            "payload_kind": "rsa_crt",
            "expected_token": '"p":',
            "risk_reason": "rsa_crt_components_private",
            "key_type": "RSA",
            "alg": "RS256",
            "required_fields": ["kty", "alg", "n", "e", "p", "q", "dp", "dq"],
            "sensitive_fields": ["p", "q", "dp", "dq"],
            "field_lengths": {"p": 48, "q": 48, "dp": 48, "dq": 48, "n": 48},
        },
        {
            "name": "tp_sensitive_rsa_short_d",
            "sensitive": True,
            "payload_kind": "rsa_short_d",
            "expected_token": '"d":',
            "risk_reason": "private_exponent_d_even_if_short",
            "key_type": "RSA",
            "alg": "RS256",
            "required_fields": ["kty", "alg", "n", "e", "d"],
            "sensitive_fields": ["d"],
            "field_lengths": {"d": 8, "n": 48},
        },
    ]
    controls: list[VariantSpec] = [
        {
            "name": "tn_non_sensitive_public_only",
            "sensitive": False,
            "payload_kind": "public_only",
            "expected_token": '"kty":"RSA"',
            "risk_reason": "public_material_only",
            "key_type": "RSA",
            "alg": "RS256",
            "required_fields": ["kty", "alg", "n", "e"],
            "sensitive_fields": [],
            "field_lengths": {"n": 48},
        },
        {
            "name": "tn_non_sensitive_rsa_missing_d",
            "sensitive": False,
            "payload_kind": "public_only",
            "expected_token": '"kty":"RSA"',
            "risk_reason": "rsa_missing_private_params",
            "key_type": "RSA",
            "alg": "RS256",
            "required_fields": ["kty", "alg", "n", "e"],
            "sensitive_fields": [],
            "field_lengths": {"n": 48},
        },
        {
            "name": "tn_non_sensitive_oct_missing_k",
            "sensitive": False,
            "payload_kind": "oct_missing_k",
            "expected_token": '"kty":"oct"',
            "risk_reason": "oct_without_secret_k",
            "key_type": "oct",
            "alg": "HS256",
            "required_fields": ["kty", "alg"],
            "sensitive_fields": [],
            "field_lengths": {},
        },
    ]
    return sensitive, controls


def _payload_for_variant(variant: VariantSpec) -> str:
    payload_kind = variant["payload_kind"]
    if payload_kind == "rsa_d":
        return _jwk_rsa_private_json(d_len=64)
    if payload_kind == "ec_d":
        return _jwk_ec_private_json(d_len=64)
    if payload_kind == "oct_k":
        return _jwk_oct_json(include_k=True, k_len=64)
    if payload_kind == "rsa_crt":
        return _jwk_rsa_private_crt_json()
    if payload_kind == "rsa_short_d":
        return _jwk_rsa_private_json(d_len=8)
    if payload_kind == "public_only":
        return _jwk_rsa_public_json()
    if payload_kind == "oct_missing_k":
        return _jwk_oct_json(include_k=False)
    raise ValueError(f"Unsupported payload kind: {payload_kind}")


def _wrap_payload_for_lang(lang: str, payload: str, idx: int, alg: str) -> str:
    if lang == "python":
        return (
            "import jwt\n\n"
            f"key_{idx} = {payload}\n"
            f"print(jwt.PyJWK.from_dict(key_{idx}, algorithm={alg!r}).key)\n"
        )
    if lang == "javascript":
        return (
            'import { importJWK } from "jose";\n'
            f"const key{idx} = {payload};\n"
            f"void importJWK(key{idx}, {alg!r});\n"
        )
    if lang == "typescript":
        return (
            'import { importJWK } from "jose";\n'
            f"const key{idx}: any = {payload};\n"
            f"void importJWK(key{idx}, {alg!r});\n"
        )
    if lang == "java":
        escaped_jwk = payload.replace('"', '\\"')
        return (
            "import com.nimbusds.jose.jwk.JWK;\n"
            "class Fixture {\n"
            "  void run() throws Exception {\n"
            f"    // JWK_PAYLOAD: {payload}\n"
            f'    String jwk = "{escaped_jwk}";\n'
            "    JWK.parse(jwk);\n"
            "  }\n"
            "}\n"
        )
    if lang == "csharp":
        escaped_jwk = payload.replace('"', '\\"')
        return (
            "using Microsoft.IdentityModel.Tokens;\n"
            "public class Fixture {\n"
            "  public void Run() {\n"
            f"    // JWK_PAYLOAD: {payload}\n"
            f'    var jwk = "{escaped_jwk}";\n'
            "    var key = new JsonWebKey(jwk);\n"
            "  }\n"
            "}\n"
        )
    if lang == "go":
        return (
            'package main\nimport "github.com/golang-jwt/jwt/v5"\n'
            "func main() {\n"
            f"  m := map[string]any{payload}\n"
            "  _ = jwt.MapClaims{\"jwk\": m}\n"
            "}\n"
        )
    if lang == "json":
        return payload
    if lang == "plaintext":
        return f"blob={payload}\n"
    raise ValueError(f"Unsupported language: {lang}")


def _render(lang: str, variant: VariantSpec, idx: int) -> tuple[str, bool, str]:
    payload = _payload_for_variant(variant)
    body = _wrap_payload_for_lang(lang, payload, idx, variant["alg"])
    return body, variant["sensitive"], variant["expected_token"]


def _stress_decoy_object(filler_width: int) -> str:
    near_private = _rand_b64url(31)
    return (
        '{'
        f'"kty":"RSA","kid":"{_rand_b64url(12)}","alg":"RS256",'
        f'"n":"{_rand_b64url(filler_width)}","e":"AQAB",'
        f'"d":"{near_private}","p":"{near_private}","q":"{near_private}",'
        f'"dp":"{near_private}","dq":"{near_private}"'
        '}'
    )


def _stress_positive_object() -> str:
    return (
        '{'
        f'"kty":"RSA","kid":"{_rand_b64url(12)}","alg":"RS256",'
        f'"n":"{_rand_b64url(64)}","e":"AQAB",'
        f'"d":"{_rand_b64url(64)}","p":"{_rand_b64url(64)}","q":"{_rand_b64url(64)}",'
        f'"dp":"{_rand_b64url(64)}","dq":"{_rand_b64url(64)}"'
        '}'
    )


def _stress_payload(profile: str, tier: StressTierSpec) -> str:
    decoys = [_stress_decoy_object(tier["filler_width"]) for _ in range(tier["decoy_count"])]
    if profile == "stress_nearmiss_dense":
        return '{"dataset":[' + ",".join(decoys) + '],"shape":"near_miss_dense"}'
    if profile == "stress_nested_maze":
        nested = _stress_decoy_object(tier["filler_width"])
        for depth in range(tier["max_depth"]):
            nested = (
                '{"layer_'
                + str(depth)
                + '":{"left":'
                + nested
                + ',"right":'
                + decoys[depth % len(decoys)]
                + "}}"
            )
        return '{"maze":' + nested + ',"tail_noise":[' + ",".join(decoys[: max(1, len(decoys) // 3)]) + "]}"
    if profile == "stress_late_true_positive":
        return (
            '{"prefix":['
            + ",".join(decoys)
            + '],"late_match":'
            + _stress_positive_object()
            + ',"suffix":{"marker":"true_positive_tail"}}'
        )
    raise ValueError(f"Unsupported stress profile: {profile}")


def _render_stress(
    lang: str, profile: StressProfileSpec, tier: StressTierSpec, idx: int
) -> tuple[str, bool, str]:
    payload = _stress_payload(profile["profile"], tier)
    body = _wrap_payload_for_lang(lang, payload, idx, "RS256")
    return body, profile["expected_match"], profile["expected_token"]


def _line_of_token(content: str, token: str) -> int:
    for idx, line in enumerate(content.splitlines(), start=1):
        if token in line:
            return idx
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate pathological JWK corpus.")
    parser.add_argument(
        "--output",
        default="src/jwk-secrets/generated",
        help="Output root for generated corpus",
    )
    parser.add_argument(
        "--files-per-language",
        type=int,
        default=50,
        help="Number of files per language",
    )
    parser.add_argument(
        "--tp-ratio",
        type=float,
        default=0.2,
        help="True-positive ratio between 0 and 1",
    )
    parser.add_argument(
        "--manifest-name",
        default="ground-truth-generated.json",
        help="Name of generated manifest file in output root",
    )
    parser.add_argument(
        "--no-clean-output",
        action="store_true",
        help="Do not remove existing output directory before generation",
    )
    parser.add_argument(
        "--include-stress-fixtures",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Generate stress fixtures for all stress tiers and profiles",
    )
    args = parser.parse_args()

    random.seed(1337)
    output_root = Path(args.output)
    if output_root.exists() and not args.no_clean_output:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_cases: list[dict[str, object]] = []
    sensitive_variants, control_variants = _build_variant_specs()

    for lang, ext in LANG_EXT.items():
        lang_dir = output_root / lang
        lang_dir.mkdir(parents=True, exist_ok=True)
        requested_sensitive = int(args.files_per_language * args.tp_ratio)
        max_sensitive = max(0, args.files_per_language - 1)
        min_sensitive = min(len(sensitive_variants), max_sensitive)
        tp_cutoff = min(max(requested_sensitive, min_sensitive), args.files_per_language)
        for i in range(args.files_per_language):
            is_sensitive = i < tp_cutoff
            variant_pool = sensitive_variants if is_sensitive else control_variants
            variant = variant_pool[i % len(variant_pool)]
            body, expected_match, token = _render(lang, variant, i)
            label = "tp" if is_sensitive else "fn"
            out_file = lang_dir / f"{label}_{i:05d}.{ext}"
            out_file.write_text(body, encoding="utf-8")
            rel_path = out_file.relative_to(output_root).as_posix()
            manifest_cases.append(
                {
                    "id": f"{lang}-{out_file.stem}",
                    "path": rel_path,
                    "expected_match": expected_match,
                    "variant": variant["name"],
                    "sensitivity_class": "critical_private_material"
                    if variant["sensitive"]
                    else "non_sensitive_control",
                    "risk_reason": variant["risk_reason"],
                    "expected_sequence": token,
                    "expected_line": _line_of_token(body, token),
                    "encoding_class": "base64url",
                    "strict_positive_schema": bool(variant["sensitive"]),
                    "expected_kty": variant["key_type"],
                    "expected_alg": variant["alg"],
                    "required_fields": variant["required_fields"],
                    "sensitive_fields": variant["sensitive_fields"],
                    "field_length_expectations": variant["field_lengths"],
                }
            )

        if args.include_stress_fixtures:
            stress_offset = args.files_per_language
            for tier_idx, tier in enumerate(STRESS_TIERS):
                for profile_idx, profile in enumerate(STRESS_PROFILES):
                    i = stress_offset + tier_idx * len(STRESS_PROFILES) + profile_idx
                    body, expected_match, token = _render_stress(lang, profile, tier, i)
                    out_file = lang_dir / f"{profile['profile']}_{tier['tier']}.{ext}"
                    out_file.write_text(body, encoding="utf-8")
                    rel_path = out_file.relative_to(output_root).as_posix()
                    manifest_cases.append(
                        {
                            "id": f"{lang}-{out_file.stem}",
                            "path": rel_path,
                            "expected_match": expected_match,
                            "variant": profile["profile"],
                            "fixture_class": "performance_stress",
                            "stress_profile": profile["profile"],
                            "stress_tier": tier["tier"],
                            "approx_size_bytes": len(body.encode("utf-8")),
                            "decoy_count": tier["decoy_count"],
                            "max_depth": tier["max_depth"],
                            "sensitivity_class": "critical_private_material"
                            if expected_match
                            else "non_sensitive_control",
                            "risk_reason": profile["risk_reason"],
                            "expected_sequence": token,
                            "expected_line": _line_of_token(body, token),
                        }
                    )

    per_lang_stress = len(STRESS_TIERS) * len(STRESS_PROFILES) if args.include_stress_fixtures else 0
    total = (args.files_per_language + per_lang_stress) * len(LANG_EXT)
    manifest_path = output_root / args.manifest_name
    manifest_path.write_text(
        json.dumps(
            {
                "cases": manifest_cases,
                "notes": {
                    "sensitive_variants": [x["name"] for x in sensitive_variants],
                    "control_variants": [x["name"] for x in control_variants],
                    "label_policy": "security_truth",
                    "known_gap_expected": False,
                    "stress_fixtures_enabled": args.include_stress_fixtures,
                    "stress_tiers": [x["tier"] for x in STRESS_TIERS],
                    "stress_profiles": [x["profile"] for x in STRESS_PROFILES],
                    "obfuscation_modeled": False,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Generated {total} files under {output_root}")
    print(f"Wrote generated manifest: {manifest_path}")


if __name__ == "__main__":
    main()
