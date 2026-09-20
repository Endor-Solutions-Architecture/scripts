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
    assert b"merged past" not in data.lower()
