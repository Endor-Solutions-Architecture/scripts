from __future__ import annotations

import csv
import json

import pytest

from analyze import analyze
from render_csv import read_labels_csv, write_csvs, write_summary
from helpers import full_sample_snapshot


def test_write_csvs_blank_fp(tmp_path):
    snap = full_sample_snapshot()
    write_csvs(analyze(snap), tmp_path)
    with (tmp_path / "fp_worksheet.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows
    assert all(r["fp"] == "" and r["reason"] == "" for r in rows)
    with (tmp_path / "pr_checks.csv").open(newline="", encoding="utf-8") as fh:
        checks = list(csv.DictReader(fh))
    assert any(r["outcome"] == "clean" for r in checks)
    with (tmp_path / "pr_trajectories.csv").open(newline="", encoding="utf-8") as fh:
        traj = list(csv.DictReader(fh))
    assert {r["classification"] for r in traj} >= {"acted", "still_open", "single_scan"}


def test_summary_json_has_denominators(tmp_path):
    snap = full_sample_snapshot()
    a = analyze(snap)
    write_summary(a, snap, tmp_path)
    data = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert data["checks_total"] == 8
    assert data["would_have_blocked_pct"] == 75.0
    assert data["d_cleared"] == 1


def test_read_labels_csv(tmp_path):
    p = tmp_path / "labels.csv"
    p.write_text("finding_uuid,scan_result_uuid,fp,reason\nf1,s1,yes,noise\n", encoding="utf-8")
    rows = read_labels_csv(p)
    assert rows[0]["fp"] == "yes"


def test_read_labels_csv_accepts_utf8_bom(tmp_path):
    p = tmp_path / "labels.csv"
    p.write_text(
        "finding_uuid,scan_result_uuid,fp,reason\nf1,s1,yes,noise\n",
        encoding="utf-8-sig",
    )

    rows = read_labels_csv(p)

    assert rows[0]["finding_uuid"] == "f1"


@pytest.mark.parametrize(
    "second_label",
    [
        "f1,s1,yes,noise",
        "f1,s1,no,real finding",
    ],
)
def test_read_labels_csv_rejects_duplicate_join_keys(tmp_path, second_label):
    p = tmp_path / "labels.csv"
    p.write_text(
        "finding_uuid,scan_result_uuid,fp,reason\n"
        "f1,s1,yes,noise\n"
        f"{second_label}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate"):
        read_labels_csv(p)


def test_read_labels_csv_requires_join_and_label_columns(tmp_path):
    p = tmp_path / "labels.csv"
    p.write_text("finding_uuid,fp\nf1,yes\n", encoding="utf-8")

    with pytest.raises(ValueError, match="required columns"):
        read_labels_csv(p)
