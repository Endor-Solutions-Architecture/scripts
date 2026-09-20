from __future__ import annotations

from analyze import analyze
from render_pdf import write_pdf
from helpers import full_sample_snapshot


def test_pdf_contains_cover_and_caveats(tmp_path):
    snap = full_sample_snapshot()
    path = tmp_path / "readiness_report.pdf"
    write_pdf(analyze(snap, snapshot_count=2), snap, path)
    data = path.read_bytes()
    assert data.startswith(b"%PDF")
    assert b"Example Corp" in data
    assert b"Block Mode Readiness" in data
    assert b"fp_worksheet.csv" in data
    assert b"21 days" in data or b"21-day" in data
    assert b"weekly snapshots" in data
    assert b"policy column is the violation type" in data
    assert b"blocked on returned labels" in data
    assert b"Sample size" in data or b"sample size" in data
    assert b"37.5% (3 / 8)" in data or b"37.5% \\(3 / 8\\)" in data
    assert b"Top 2 of 2" in data
    assert b"6 of 6 warns" in data
    assert b"71.4%" in data
    assert b"merged" not in data.lower()
    assert b"ignored-at-merge" not in data.lower()
    assert b"merged past" not in data.lower()


def test_pdf_lists_unmatched_labels(tmp_path):
    snap = full_sample_snapshot()
    labels = [
        {
            "finding_uuid": "missing-finding",
            "scan_result_uuid": "missing-scan",
            "fp": "yes",
            "reason": "",
        }
    ]
    path = tmp_path / "readiness_report.pdf"
    write_pdf(analyze(snap, labels=labels, snapshot_count=2), snap, path)
    data = path.read_bytes()
    assert b"missing-finding" in data
    assert b"missing-scan" in data


def test_pdf_gate1_rates_include_labeled_counts(tmp_path):
    snap = full_sample_snapshot()
    rows = analyze(snap).fp_rows
    labels = [
        {
            "finding_uuid": rows[0]["finding_uuid"],
            "scan_result_uuid": rows[0]["scan_result_uuid"],
            "fp": "yes",
            "reason": "noise",
        },
        {
            "finding_uuid": rows[1]["finding_uuid"],
            "scan_result_uuid": rows[1]["scan_result_uuid"],
            "fp": "no",
            "reason": "valid",
        },
    ]
    path = tmp_path / "readiness_report.pdf"

    write_pdf(analyze(snap, labels=labels), snap, path)

    data = path.read_bytes()
    assert b"1 / 2 labeled findings" in data
    assert b"0 / 1 labeled PRs" in data
    assert b"SAST 0.0%" in data
    assert b"0 / 1 labeled" in data
    assert b"per PR 0.0%" in data


def test_pdf_gate1_with_no_yes_no_labels_shows_zero_denominator(tmp_path):
    snap = full_sample_snapshot()
    row = analyze(snap).fp_rows[0]
    labels = [
        {
            "finding_uuid": row["finding_uuid"],
            "scan_result_uuid": row["scan_result_uuid"],
            "fp": "unsure",
            "reason": "",
        }
    ]
    path = tmp_path / "readiness_report.pdf"

    write_pdf(analyze(snap, labels=labels), snap, path)

    data = path.read_bytes()
    assert b"0 / 0 labeled findings" in data
    assert b"0 / 0 labeled PRs" in data


def test_pdf_mark_date_split_lists_block_count(tmp_path):
    snap = full_sample_snapshot()
    snap.scans["s8"].outcome = "block"
    snap.scans["s8"].blocking_finding_ids = ["f-block"]
    path = tmp_path / "readiness_report.pdf"

    write_pdf(analyze(snap), snap, path)

    assert b"1 block" in path.read_bytes()


def test_pdf_escapes_dynamic_text_and_wraps_long_repo_names(tmp_path):
    snap = full_sample_snapshot()
    snap.meta.customer = "<customer &"
    snap.policies[0].name = "<policy &"
    snap.projects["p-alpha"].full_name = "<repository & " + ("x" * 300)
    path = tmp_path / "readiness_report.pdf"

    write_pdf(analyze(snap), snap, path)

    data = path.read_bytes()
    assert data.startswith(b"%PDF")
