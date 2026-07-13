"""Pure computation functions for the AI credit usage dashboard.

No Streamlit or subprocess dependencies here — keeps this module fast
and easy to unit test in isolation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd

PRESETS: dict[str, int] = {
    "Last 1 day": 1,
    "Last 7 days": 7,
    "Last 2 weeks": 14,
    "Last 4 weeks": 28,
    "Last 2 months": 60,
    "Last 3 months": 90,
}

BURN_RATE_TRAILING_DAYS: int = 14
FETCH_FLOOR_DAYS: int = 90
FETCH_CAP_DAYS: int = 180


def slice_window(df: pd.DataFrame, days: int, now: Optional[datetime] = None) -> pd.DataFrame:
    """Rows with accrued_date >= now - days. Requires a datetime64[ns, UTC] 'accrued_date' column."""
    if df.empty:
        return df
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    return df[df["accrued_date"] >= cutoff]


def windowed_usage(df: pd.DataFrame, days: int, now: Optional[datetime] = None) -> float:
    """Sum of llm_cost for rows within the trailing `days` window."""
    windowed = slice_window(df, days, now)
    if windowed.empty:
        return 0.0
    return float(windowed["llm_cost"].sum())


def pct_used(usage: float, max_credit: float) -> float:
    """Fraction of quota used. Returns 0.0 if max_credit <= 0."""
    if max_credit <= 0:
        return 0.0
    return usage / max_credit


def threshold_state(fraction_used: float) -> str:
    """Alert band for a used-fraction: 'critical' (>=95%), 'high' (>=80%), 'warn' (>=50%), else 'ok'."""
    pct = fraction_used * 100
    if pct >= 95:
        return "critical"
    if pct >= 80:
        return "high"
    if pct >= 50:
        return "warn"
    return "ok"


def burn_rate(df: pd.DataFrame, now: Optional[datetime] = None, trailing_days: int = BURN_RATE_TRAILING_DAYS) -> float:
    """Mean daily llm_cost over the trailing `trailing_days` calendar days (zero-usage days count as 0)."""
    total = windowed_usage(df, trailing_days, now)
    return total / trailing_days


def projected_exhaustion_date(remaining: float, daily_burn_rate: float, now: Optional[datetime] = None) -> Optional[datetime]:
    """Date the remaining credit hits zero at the current burn rate. None if burn rate is negligible (<=$0.0001/day)."""
    if daily_burn_rate <= 0.0001:
        return None
    now = now or datetime.now(timezone.utc)
    days_remaining = remaining / daily_burn_rate
    return now + timedelta(days=days_remaining)


def compute_fetch_days(license_days: int) -> int:
    """Days of history to fetch: at least FETCH_FLOOR_DAYS, at most FETCH_CAP_DAYS, scaled to the license window."""
    return min(max(license_days, FETCH_FLOOR_DAYS), FETCH_CAP_DAYS)


def is_non_standard_window(license_days: int) -> bool:
    """True when the license's rolling window exceeds what the dashboard fetches (placeholder/misconfigured quota)."""
    return license_days > FETCH_CAP_DAYS


def model_breakdown(df: pd.DataFrame, days: int, now: Optional[datetime] = None) -> pd.DataFrame:
    """Usage grouped by llm model within the trailing `days` window: columns llm, cost, pct_of_window; sorted by cost desc."""
    windowed = slice_window(df, days, now)
    if windowed.empty:
        return pd.DataFrame(columns=["llm", "cost", "pct_of_window"])
    grouped = windowed.groupby("llm", as_index=False)["llm_cost"].sum().rename(columns={"llm_cost": "cost"})
    total = grouped["cost"].sum()
    grouped["pct_of_window"] = grouped["cost"] / total if total > 0 else 0.0
    return grouped.sort_values("cost", ascending=False).reset_index(drop=True)


def daily_series(df: pd.DataFrame, days: int, now: Optional[datetime] = None) -> pd.DataFrame:
    """One row per calendar day in the trailing `days` window, zero-filled for days without usage.

    Unlike slice_window (which cuts at an exact sub-day timestamp), this buckets by whole
    UTC calendar day so every day in the window gets a row — needed for evenly-spaced trend charts.
    Columns: day (datetime64 UTC, ascending), cost (float).
    """
    now = now or datetime.now(timezone.utc)
    end_day = pd.Timestamp(now).normalize()
    start_day = end_day - pd.Timedelta(days=days - 1)
    all_days = pd.date_range(start=start_day, end=end_day, freq="D", tz="UTC")

    if df.empty:
        daily_cost = pd.Series(dtype=float)
    else:
        daily_cost = df.groupby(df["accrued_date"].dt.normalize())["llm_cost"].sum()

    result = pd.DataFrame({"day": all_days})
    result["cost"] = result["day"].map(daily_cost).fillna(0.0)
    return result


_DAY_LOCATOR_INTERVALS = {1: 1, 7: 1, 14: 2, 28: 4, 60: 7, 90: 10}


def pick_day_locator_interval(window_days: int) -> int:
    """Tick spacing (in days) for a daily trend chart's x-axis, tuned per PRESETS window size.

    Matplotlib's default AutoDateLocator picks sub-day tick spacing for narrow date ranges,
    which produces duplicate day labels when formatted at day precision. An explicit
    per-window interval keeps ticks aligned to whole days and readable at every window size.
    """
    return _DAY_LOCATOR_INTERVALS.get(window_days, max(1, window_days // 9))
