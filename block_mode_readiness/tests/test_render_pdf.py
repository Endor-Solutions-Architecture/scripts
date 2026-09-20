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
