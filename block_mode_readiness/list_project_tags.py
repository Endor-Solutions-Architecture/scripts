#!/usr/bin/env python3
"""Print unique Project.meta.tags for a namespace as CSV on stdout."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List unique project tags in a namespace (CSV on stdout)"
    )
    parser.add_argument("-n", "--namespace", required=True)
    args = parser.parse_args()

    cmd = [
        "endorctl", "-n", args.namespace,
        "api", "list", "-r", "Project",
        "--field-mask", "meta.tags",
        "--list-all", "--traverse",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return result.returncode or 1

    objects = (json.loads(result.stdout).get("list") or {}).get("objects") or []
    tags = sorted({
        tag
        for obj in objects
        for tag in ((obj.get("meta") or {}).get("tags") or [])
        if tag
    })

    writer = csv.writer(sys.stdout)
    writer.writerow(["tag"])
    for tag in tags:
        writer.writerow([tag])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
