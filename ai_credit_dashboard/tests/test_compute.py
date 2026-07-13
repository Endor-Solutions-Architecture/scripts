import pandas as pd
from datetime import datetime, timezone

import compute


def _df(rows):
    df = pd.DataFrame(rows)
    if not df.empty:
        df["accrued_date"] = pd.to_datetime(df["accrued_date"], utc=True)
    return df


def test_slice_window_keeps_rows_within_days():
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    df = _df([
        {"accrued_date": "2026-07-09T00:00:00Z", "llm": "gpt", "llm_cost": 1.0},
        {"accrued_date": "2026-06-01T00:00:00Z", "llm": "gpt", "llm_cost": 2.0},
    ])

    result = compute.slice_window(df, days=7, now=now)

    assert len(result) == 1
    assert result.iloc[0]["llm_cost"] == 1.0


def test_slice_window_empty_df_returns_empty():
    df = pd.DataFrame(columns=["accrued_date", "llm", "llm_cost"])

    result = compute.slice_window(df, days=7)

    assert result.empty


def test_windowed_usage_sums_llm_cost_in_window():
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    df = _df([
        {"accrued_date": "2026-07-09T00:00:00Z", "llm": "gpt", "llm_cost": 1.5},
        {"accrued_date": "2026-07-08T00:00:00Z", "llm": "gpt", "llm_cost": 2.5},
        {"accrued_date": "2026-06-01T00:00:00Z", "llm": "gpt", "llm_cost": 100.0},
    ])

    result = compute.windowed_usage(df, days=7, now=now)

    assert result == 4.0


def test_windowed_usage_empty_df_returns_zero():
    df = pd.DataFrame(columns=["accrued_date", "llm", "llm_cost"])

    assert compute.windowed_usage(df, days=7) == 0.0


def test_pct_used_divides_usage_by_max_credit():
    assert compute.pct_used(usage=25.0, max_credit=100.0) == 0.25


def test_pct_used_zero_max_credit_returns_zero():
    assert compute.pct_used(usage=25.0, max_credit=0.0) == 0.0


def test_threshold_state_bands():
    assert compute.threshold_state(0.10) == "ok"
    assert compute.threshold_state(0.50) == "warn"
    assert compute.threshold_state(0.80) == "high"
    assert compute.threshold_state(0.95) == "critical"
    assert compute.threshold_state(1.20) == "critical"


def test_burn_rate_averages_over_trailing_days():
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    df = _df([
        {"accrued_date": "2026-07-09T00:00:00Z", "llm": "gpt", "llm_cost": 7.0},
        {"accrued_date": "2026-07-01T00:00:00Z", "llm": "gpt", "llm_cost": 7.0},
    ])

    result = compute.burn_rate(df, now=now, trailing_days=14)

    assert result == 1.0


def test_burn_rate_zero_usage_is_zero():
    df = pd.DataFrame(columns=["accrued_date", "llm", "llm_cost"])

    assert compute.burn_rate(df) == 0.0


def test_projected_exhaustion_date_computes_days_out():
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)

    result = compute.projected_exhaustion_date(remaining=100.0, daily_burn_rate=10.0, now=now)

    assert result == datetime(2026, 7, 20, tzinfo=timezone.utc)


def test_projected_exhaustion_date_negligible_burn_returns_none():
    result = compute.projected_exhaustion_date(remaining=100.0, daily_burn_rate=0.0)

    assert result is None


def test_compute_fetch_days_clamps_between_floor_and_cap():
    assert compute.compute_fetch_days(license_days=7) == 90
    assert compute.compute_fetch_days(license_days=120) == 120
    assert compute.compute_fetch_days(license_days=1000) == 180


def test_is_non_standard_window():
    assert compute.is_non_standard_window(30) is False
    assert compute.is_non_standard_window(180) is False
    assert compute.is_non_standard_window(1000) is True


def test_model_breakdown_groups_by_llm_with_pct():
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    df = _df([
        {"accrued_date": "2026-07-09T00:00:00Z", "llm": "gpt-4.1-mini", "llm_cost": 3.0},
        {"accrued_date": "2026-07-08T00:00:00Z", "llm": "gpt-4.1-mini", "llm_cost": 1.0},
        {"accrued_date": "2026-07-07T00:00:00Z", "llm": "claude", "llm_cost": 5.0},
    ])

    result = compute.model_breakdown(df, days=7, now=now)

    assert list(result["llm"]) == ["claude", "gpt-4.1-mini"]
    assert result.iloc[0]["cost"] == 5.0
    assert round(result.iloc[0]["pct_of_window"], 4) == 0.5556
    assert result.iloc[1]["cost"] == 4.0


def test_model_breakdown_empty_df():
    df = pd.DataFrame(columns=["accrued_date", "llm", "llm_cost"])

    result = compute.model_breakdown(df, days=7)

    assert result.empty
    assert list(result.columns) == ["llm", "cost", "pct_of_window"]


def test_daily_series_zero_fills_missing_days():
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    df = _df([
        {"accrued_date": "2026-07-07T00:00:00Z", "llm": "gpt", "llm_cost": 0.29},
        {"accrued_date": "2026-07-10T00:00:00Z", "llm": "gpt", "llm_cost": 18.55},
    ])

    result = compute.daily_series(df, days=7, now=now)

    assert len(result) == 7
    assert list(result["day"].dt.strftime("%Y-%m-%d")) == [
        "2026-07-04", "2026-07-05", "2026-07-06", "2026-07-07",
        "2026-07-08", "2026-07-09", "2026-07-10",
    ]
    costs = dict(zip(result["day"].dt.strftime("%Y-%m-%d"), result["cost"]))
    assert costs["2026-07-04"] == 0.0
    assert costs["2026-07-07"] == 0.29
    assert costs["2026-07-08"] == 0.0
    assert costs["2026-07-10"] == 18.55


def test_daily_series_single_day_window():
    now = datetime(2026, 7, 9, tzinfo=timezone.utc)
    df = _df([{"accrued_date": "2026-07-09T00:00:00Z", "llm": "gpt", "llm_cost": 18.84}])

    result = compute.daily_series(df, days=1, now=now)

    assert len(result) == 1
    assert result.iloc[0]["day"].strftime("%Y-%m-%d") == "2026-07-09"
    assert result.iloc[0]["cost"] == 18.84


def test_daily_series_empty_df_still_zero_fills_range():
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    df = pd.DataFrame(columns=["accrued_date", "llm", "llm_cost"])

    result = compute.daily_series(df, days=3, now=now)

    assert len(result) == 3
    assert (result["cost"] == 0.0).all()


def test_pick_day_locator_interval_matches_presets():
    assert compute.pick_day_locator_interval(1) == 1
    assert compute.pick_day_locator_interval(7) == 1
    assert compute.pick_day_locator_interval(14) == 2
    assert compute.pick_day_locator_interval(28) == 4
    assert compute.pick_day_locator_interval(60) == 7
    assert compute.pick_day_locator_interval(90) == 10
