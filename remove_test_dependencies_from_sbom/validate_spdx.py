#!/usr/bin/env python3
"""
Validate SPDX JSON files against the SPDX 2.3 spec.

Runs the same checks as the SPDX Online Tool at https://tools.spdx.org/app/, so
an SBOM can be confirmed clean without leaving the terminal.

Usage:
    python validate_spdx.py <file.json> [<file.json> ...]

Exits non-zero if any file fails validation.
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


def validate(path):
    """Return validation messages for one file; an empty list means it is clean."""
    try:
        document = parse_file(path)
    except Exception as e:
        # A malformed license expression fails here, before validation starts.
        return [f"failed to parse: {str(e)[:400]}"]
    return [message.validation_message
            for message in validate_full_spdx_document(document)]


def summarize(messages):
    """Group messages by kind so hundreds of identical errors read as one line."""
    grouped = Counter()
    examples = {}
    for message in messages:
        key = re.sub(r'(, but is:|but is:).*$', '', message).strip()
        grouped[key] += 1
        examples.setdefault(key, message)
    return grouped, examples


def main():
    paths = sys.argv[1:]
    if not paths:
        print(__doc__.strip())
        sys.exit(2)

    any_failed = False
    for path in paths:
        messages = validate(path)
        if not messages:
            print(f"PASS  {path}")
            continue

        any_failed = True
        print(f"FAIL  {path} -- {len(messages)} validation message(s)")
        grouped, examples = summarize(messages)
        for key, count in grouped.most_common():
            print(f"      {count:5d}x  {key}")
            print(f"             e.g. {examples[key][:150]}")

    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
