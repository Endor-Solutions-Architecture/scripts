from __future__ import annotations

from pathlib import Path

import pytest

import main as cli
from helpers import full_sample_snapshot
from snapshot import save_snapshot


def test_parse_mark_dates():
    assert cli.parse_mark_dates(["sast=2026-03-10"]) == {"sast": "2026-03-10"}


def test_report_writes_into_snapshot_dir(tmp_path, monkeypatch):
    snap_dir = tmp_path / "20260321T180000"
    snap_dir.mkdir()
    save_snapshot(full_sample_snapshot(), snap_dir)
    rc = cli.main(["report", "--snapshot", str(snap_dir)])
    assert rc == 0
    assert (snap_dir / "readiness_report.pdf").exists()
    assert (snap_dir / "pr_checks.csv").exists()
    assert (snap_dir / "fp_worksheet.csv").exists()
    assert (snap_dir / "pr_trajectories.csv").exists()
    assert (snap_dir / "summary.json").exists()


def test_report_snapshot_dir_writes_union_folder(tmp_path):
    w1 = tmp_path / "20260301T180000"
    w1.mkdir()
    save_snapshot(full_sample_snapshot(), w1)
    rc = cli.main(["report", "--snapshot-dir", str(tmp_path)])
    assert rc == 0
    unions = list(tmp_path.glob("union-*"))
    assert len(unions) == 1
    assert (unions[0] / "readiness_report.pdf").exists()
    assert not (unions[0] / "snapshot.json").exists()


def test_collect_error_exit_code(monkeypatch):
    def boom(*a, **k):
        from collect import CollectError
        raise CollectError("no projects matched project tags: x")
    monkeypatch.setattr(cli, "collect", boom)
    rc = cli.main(["collect", "-n", "example-corp", "--project-tags", "rollout-wave-1"])
    assert rc == 1


def test_parse_project_tags():
    assert cli.parse_project_tags("rollout-wave-1, rollout-wave-2,") == [
        "rollout-wave-1",
        "rollout-wave-2",
    ]


def test_parse_mark_dates_invalid():
    with pytest.raises(SystemExit) as exc:
        cli.parse_mark_dates(["sast"])
    assert exc.value.code == 1


def test_output_root():
    assert cli.output_root("example-corp") == (
        Path("generated_reports") / "block_mode_readiness" / "example-corp"
    )


def test_days_over_21_warns_and_continues(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    def fake_collect(namespace, tags, days, **kwargs):
        assert days == 30
        return full_sample_snapshot()

    monkeypatch.setattr(cli, "collect", fake_collect)
    rc = cli.main(
        [
            "collect",
            "-n",
            "example-corp",
            "--project-tags",
            "rollout-wave-1",
            "--days",
            "30",
        ]
    )
    assert rc == 0
    assert "21" in capsys.readouterr().err
    outs = list(
        (tmp_path / "generated_reports" / "block_mode_readiness" / "example-corp").iterdir()
    )
    assert len(outs) == 1
    assert (outs[0] / "snapshot.json").exists()


def test_collect_does_not_mkdir_on_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def boom(*a, **k):
        from collect import CollectError
        raise CollectError("no projects matched project tags: x")

    monkeypatch.setattr(cli, "collect", boom)
    rc = cli.main(["collect", "-n", "example-corp", "--project-tags", "rollout-wave-1"])
    assert rc == 1
    assert not (tmp_path / "generated_reports").exists()


def test_collect_reserves_unique_output_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "collect", lambda *a, **k: full_sample_snapshot())
    monkeypatch.setattr(cli, "_timestamp", lambda: "20260321T180000")
    argv = [
        "collect",
        "-n",
        "example-corp",
        "--project-tags",
        "rollout-wave-1",
    ]

    assert cli.main(argv) == 0
    assert cli.main(argv) == 0

    root = (
        tmp_path
        / "generated_reports"
        / "block_mode_readiness"
        / "example-corp"
    )
    outputs = sorted(path.name for path in root.iterdir())
    assert outputs == ["20260321T180000", "20260321T180000-1"]
    assert all((root / name / "snapshot.json").is_file() for name in outputs)


def test_collect_error_prints_command(monkeypatch, capsys):
    def boom(*a, **k):
        from collect import CollectError
        raise CollectError(
            "failed",
            command=["endorctl", "-n", "example-corp", "api", "list"],
        )

    monkeypatch.setattr(cli, "collect", boom)
    rc = cli.main(["collect", "-n", "example-corp", "--project-tags", "rollout-wave-1"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "endorctl -n example-corp api list" in err
    assert "failed" in err


def test_missing_required_flags_exit_2():
    assert cli.main(["collect"]) == 2
    assert cli.main(["report"]) == 2


def test_report_empty_dir_exit_1(tmp_path):
    assert cli.main(["report", "--snapshot-dir", str(tmp_path)]) == 1


def test_report_uses_labels(tmp_path):
    import json

    from analyze import analyze

    snap_dir = tmp_path / "20260321T180000"
    snap_dir.mkdir()
    save_snapshot(full_sample_snapshot(), snap_dir)
    row = analyze(full_sample_snapshot()).fp_rows[0]
    labels = tmp_path / "labels.csv"
    labels.write_text(
        "finding_uuid,scan_result_uuid,fp,reason\n"
        f"{row['finding_uuid']},{row['scan_result_uuid']},yes,noise\n",
        encoding="utf-8",
    )
    rc = cli.main(
        ["report", "--snapshot", str(snap_dir), "--labels", str(labels)]
    )
    assert rc == 0
    summary = json.loads((snap_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["gate1_per_finding"] == 100.0


def test_report_missing_labels_file_exits_cleanly(tmp_path, capsys):
    snap_dir = tmp_path / "20260321T180000"
    snap_dir.mkdir()
    save_snapshot(full_sample_snapshot(), snap_dir)
    missing = tmp_path / "missing-labels.csv"

    rc = cli.main(
        ["report", "--snapshot", str(snap_dir), "--labels", str(missing)]
    )

    assert rc == 1
    assert str(missing) in capsys.readouterr().err


def test_report_invalid_labels_file_exits_cleanly(tmp_path, capsys):
    snap_dir = tmp_path / "20260321T180000"
    snap_dir.mkdir()
    save_snapshot(full_sample_snapshot(), snap_dir)
    labels = tmp_path / "labels.csv"
    labels.write_text("finding_uuid,fp\nf1,yes\n", encoding="utf-8")

    rc = cli.main(
        ["report", "--snapshot", str(snap_dir), "--labels", str(labels)]
    )

    assert rc == 1
    assert "required columns" in capsys.readouterr().err


def test_run_writes_snapshot_and_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "collect", lambda *a, **k: full_sample_snapshot())
    rc = cli.main(
        ["run", "-n", "example-corp", "--project-tags", "rollout-wave-1"]
    )
    assert rc == 0
    outs = list(
        (tmp_path / "generated_reports" / "block_mode_readiness" / "example-corp").iterdir()
    )
    assert len(outs) == 1
    assert (outs[0] / "snapshot.json").exists()
    assert (outs[0] / "readiness_report.pdf").exists()
    assert (outs[0] / "summary.json").exists()
    assert (outs[0] / "pr_checks.csv").exists()
