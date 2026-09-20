from __future__ import annotations

import pytest

from snapshot import SnapshotError, load_snapshot, load_snapshot_dir, union_snapshots, save_snapshot
from helpers import make_meta, make_scan, make_snapshot


def test_save_and_load_roundtrip(tmp_path):
    snap = make_snapshot()
    save_snapshot(snap, tmp_path)
    assert (tmp_path / "snapshot.json").exists()
    assert (tmp_path / "meta.json").exists()
    loaded = load_snapshot(tmp_path)
    assert loaded.meta.namespace == "example-corp"
    assert loaded.scans["s1"].pr_number == "10"
    assert loaded.projects["p-beta"].full_name == "org/beta"


def test_union_keeps_first_scan_uuid():
    older = make_snapshot(
        meta=make_meta(generated_at="2026-02-21T00:00:00Z"),
        scans={
            "s1": make_scan(create_time="2026-02-01T00:00:00Z"),
            "s-old": make_scan(
                uuid="s-old",
                create_time="2026-02-01T00:00:00Z",
                pr_number="1",
            ),
        },
    )
    newer = make_snapshot(
        scans={"s1": make_scan(create_time="2026-03-01T12:00:00Z")},
    )
    merged = union_snapshots([older, newer])
    assert merged.scans["s1"].create_time == "2026-02-01T00:00:00Z"
    assert "s-old" in merged.scans
    assert merged.meta.ci_runs_dropped_no_pr == 0


def test_union_rejects_mixed_namespaces():
    a = make_snapshot()
    b = make_snapshot(meta=make_meta(namespace="other-corp"))
    with pytest.raises(SnapshotError, match="namespace"):
        union_snapshots([a, b])


def test_load_snapshot_dir_skips_union_folders(tmp_path):
    week1 = tmp_path / "20260301T180000"
    week1.mkdir()
    save_snapshot(make_snapshot(), week1)
    union_dir = tmp_path / "union-20260321T180000"
    union_dir.mkdir()
    save_snapshot(
        make_snapshot(scans={"should-not-load": make_scan(uuid="should-not-load")}),
        union_dir,
    )
    loaded = load_snapshot_dir(tmp_path)
    assert "should-not-load" not in loaded.scans
    assert "s1" in loaded.scans


def test_load_snapshot_dir_empty_raises(tmp_path):
    with pytest.raises(SnapshotError):
        load_snapshot_dir(tmp_path)
