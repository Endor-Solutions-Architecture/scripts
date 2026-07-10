import json
import subprocess
from types import SimpleNamespace

import pandas as pd

import dashboard


def _fake_run(response_obj):
    def _run(cmd, capture_output, text, check, timeout):
        return SimpleNamespace(stdout=json.dumps(response_obj), stderr="")
    return _run


def _fake_run_capturing_cmd(response_obj, captured):
    """Like _fake_run, but records the `cmd` argument into `captured["cmd"]`."""
    def _run(cmd, capture_output, text, check, timeout):
        captured["cmd"] = cmd
        return SimpleNamespace(stdout=json.dumps(response_obj), stderr="")
    return _run


def test_fetch_license_parses_ai_limit(monkeypatch):
    response = {"list": {"objects": [{"spec": {"quota": {"ai_limit": {"days": 30, "max_credit": "500"}}}}]}}
    monkeypatch.setattr(dashboard.subprocess, "run", _fake_run(response))

    result = dashboard.fetch_license("acme-corp")

    assert result == {"days": 30, "max_credit": 500.0}


def test_fetch_license_returns_none_when_no_objects(monkeypatch):
    monkeypatch.setattr(dashboard.subprocess, "run", _fake_run({"list": {"objects": []}}))

    assert dashboard.fetch_license("acme-corp") is None


def test_fetch_usage_parses_rows_into_dataframe(monkeypatch):
    response = {
        "list": {"objects": [
            {"spec": {"accrued_date": "2026-06-01T00:00:00Z", "llm": "AVAILABLE_LLM_OPENAI_GPT_4_1_MINI", "llm_cost": 0.5}},
            {"spec": {"accrued_date": "2026-06-02T00:00:00Z", "llm": "AVAILABLE_LLM_OPENAI_GPT_4_1_MINI", "llm_cost": 1.5}},
        ]}
    }
    monkeypatch.setattr(dashboard.subprocess, "run", _fake_run(response))

    df = dashboard.fetch_usage("acme-corp", 90)

    assert list(df.columns) == ["accrued_date", "llm", "llm_cost"]
    assert len(df) == 2
    assert df["llm_cost"].sum() == 2.0
    assert df["accrued_date"].dtype.kind == "M"


def test_fetch_usage_empty_response_returns_empty_dataframe(monkeypatch):
    monkeypatch.setattr(dashboard.subprocess, "run", _fake_run({"list": {"objects": []}}))

    df = dashboard.fetch_usage("acme-corp", 90)

    assert df.empty
    assert list(df.columns) == ["accrued_date", "llm", "llm_cost"]


def test_fetch_usage_command_includes_list_all_flag(monkeypatch):
    """--list-all is safety-critical: the default endorctl page size is 100, which
    silently truncates results beyond ~a week of daily AICreditMetric records."""
    captured = {}
    monkeypatch.setattr(
        dashboard.subprocess, "run",
        _fake_run_capturing_cmd({"list": {"objects": []}}, captured),
    )

    dashboard.fetch_usage("acme-corp", 90)

    assert "cmd" in captured
    assert "--list-all" in captured["cmd"]


def test_run_endorctl_returns_none_on_called_process_error(monkeypatch):
    def _raise(cmd, capture_output, text, check, timeout):
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd, stderr="permission denied")

    monkeypatch.setattr(dashboard.subprocess, "run", _raise)

    result = dashboard.run_endorctl(["api", "list", "-r", "EndorLicense"], "acme-corp")

    assert result is None


def test_run_endorctl_returns_none_on_timeout(monkeypatch):
    def _raise(cmd, capture_output, text, check, timeout):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

    monkeypatch.setattr(dashboard.subprocess, "run", _raise)

    result = dashboard.run_endorctl(["api", "list", "-r", "EndorLicense"], "acme-corp")

    assert result is None


def test_run_endorctl_returns_none_on_invalid_json(monkeypatch):
    def _run(cmd, capture_output, text, check, timeout):
        return SimpleNamespace(stdout="not valid json {{{", stderr="")

    monkeypatch.setattr(dashboard.subprocess, "run", _run)

    result = dashboard.run_endorctl(["api", "list", "-r", "EndorLicense"], "acme-corp")

    assert result is None


def test_fetch_license_returns_none_when_days_or_max_credit_missing(monkeypatch):
    response = {"list": {"objects": [{"spec": {"quota": {"ai_limit": {"days": 30}}}}]}}
    monkeypatch.setattr(dashboard.subprocess, "run", _fake_run(response))

    assert dashboard.fetch_license("acme-corp") is None


def test_generate_pdf_returns_pdf_bytes():
    df = pd.DataFrame([
        {"accrued_date": pd.Timestamp("2026-07-05", tz="UTC"), "llm": "gpt-4.1-mini", "llm_cost": 1.0},
        {"accrued_date": pd.Timestamp("2026-07-06", tz="UTC"), "llm": "gpt-4.1-mini", "llm_cost": 2.0},
    ])
    license_info = {"days": 30, "max_credit": 100.0}

    pdf_bytes = dashboard.generate_pdf("acme-corp", license_info, df, "Last 7 days", 7)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500
