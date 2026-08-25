#!/usr/bin/env python3
"""
Validate SPDX JSON files and check NTIA minimum-elements conformance.

Runs the same two checks as the SPDX Online Tool at https://tools.spdx.org/app/,
so an SBOM can be confirmed clean without uploading it:

  * SPDX 2.3 validation  -- is the document well formed and spec legal
  * NTIA conformance     -- does it carry the seven minimum elements

Usage:
    python validate_spdx.py <file.json> [<file.json> ...]
    python validate_spdx.py --no-ntia <file.json>     # validation only

Exits non-zero if any file fails either check.
"""

import re
import sys
from collections import Counter

try:
    from spdx_tools.spdx.parser.parse_anything import parse_file
    from spdx_tools.spdx.validation.document_validator import validate_full_spdx_document
except ImportError:
    print("This script needs the spdx-tools package:")
    print("    pip install -r requirements.txt")
    sys.exit(2)

try:
    from ntia_conformance_checker import SbomChecker
except ImportError:
    SbomChecker = None


def validate(path):
    """Return validation messages for one file; an empty list means it is clean."""
    try:
        parsed = parse_file(path)
    except Exception as e:
        # A malformed license expression fails here, before validation starts.
        return [f"failed to parse: {str(e)[:400]}"]
    return [message.validation_message
            for message in validate_full_spdx_document(parsed)]


def summarize(messages):
    """Group messages by kind so hundreds of identical errors read as one line."""
    grouped = Counter()
    examples = {}
    for message in messages:
        key = re.sub(r'(, but is:|but is:).*$', '', message).strip()
        grouped[key] += 1
        examples.setdefault(key, message)
    return grouped, examples


def check_ntia(path):
    """Report NTIA minimum-elements conformance for one file.

    Returns a dict, or None when the checker isn't installed. Note that the
    checker only calls a document conformant if it is *also* SPDX valid, so the
    element verdict and the overall verdict are reported separately -- otherwise
    a file with all seven elements present looks inexplicably non-conformant.
    """
    if SbomChecker is None:
        return None

    try:
        checker = SbomChecker(path)
    except Exception as e:
        return {"elements": [("checker failed", str(e)[:120])],
                "elements_ok": False, "compliant": False, "blocking_errors": 0}

    elements = []
    for label, attribute in [("author of SBOM data", "doc_author"),
                             ("timestamp", "doc_timestamp"),
                             ("dependency relationships", "dependency_relationships")]:
        elements.append((label, "present" if getattr(checker, attribute, False) else "MISSING"))

    for label, attribute in [("component names", "components_without_names"),
                             ("component versions", "components_without_versions"),
                             ("component suppliers", "components_without_suppliers"),
                             ("unique identifiers", "components_without_identifiers")]:
        missing = getattr(checker, attribute, None) or []
        elements.append((label, "present" if not missing
                         else f"MISSING on {len(missing)} component(s)"))

    # Derive the element verdict here: the checker's own element property is a
    # deprecated alias for `compliant`, which also folds in SPDX validation.
    elements_ok = all(detail == "present" for _, detail in elements)

    return {
        "elements": elements,
        "elements_ok": bool(elements_ok),
        "compliant": bool(checker.compliant),
        "blocking_errors": len(getattr(checker, "validation_messages", []) or []),
    }


def main():
    paths = [a for a in sys.argv[1:] if not a.startswith("-")]
    want_ntia = "--no-ntia" not in sys.argv
    if not paths:
        print(__doc__.strip())
        sys.exit(2)

    if want_ntia and SbomChecker is None:
        print("Note: ntia-conformance-checker is not installed, skipping the "
              "conformance check (pip install -r requirements.txt)\n")

    any_failed = False
    for path in paths:
        messages = validate(path)
        if messages:
            any_failed = True
            print(f"FAIL  {path} -- {len(messages)} validation message(s)")
            grouped, examples = summarize(messages)
            for key, count in grouped.most_common():
                print(f"      {count:5d}x  {key}")
                print(f"             e.g. {examples[key][:150]}")
        else:
            print(f"PASS  {path} -- SPDX 2.3 validation")

        if not want_ntia:
            continue

        report = check_ntia(path)
        if report is None:
            continue
        if not report["compliant"]:
            any_failed = True

        verdict = "PASS" if report["compliant"] else "FAIL"
        print(f"{verdict}  {path} -- NTIA minimum elements")
        for label, detail in report["elements"]:
            marker = " " if detail == "present" else "!"
            print(f"    {marker} {label:26} {detail}")

        # All seven present but still not conformant means the document itself
        # is invalid -- the checker requires a valid document before it counts.
        if report["elements_ok"] and not report["compliant"]:
            print(f"    ! all seven elements are present, but conformance is blocked by "
                  f"{report['blocking_errors']} SPDX validation error(s)")

    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
