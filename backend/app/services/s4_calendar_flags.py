"""S4 calendar / scheduled-event flags (US equity research skeleton).

Uses calendar conventions by default (no exchange holiday calendar dependency):
- **Month-end (calendar)**: last **calendar** day of the month (not necessarily last trading day).
- **Month-end (trading)**: last **observed** bar date of the month in a sorted series (next bar is in a new month).
- **Quarter-end**: month-end in Mar/Jun/Sep/Dec (paired with the active month-end mode).
- **OpEx week**: Monday–Friday week containing the **third Friday** (standard
  monthly US equity options expiry pattern).

All functions are pure; enable/disable dimensions via caller (from config).
"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from datetime import date, timedelta


def third_friday(year: int, month: int) -> date:
    """Third Friday of ``month`` (1–12) in ``year`` (US monthly options cycle)."""
    first_weekday, days_in_month = calendar.monthrange(year, month)
    # weekday: Mon=0 .. Sun=6; we want first Friday
    # first_friday = 1 + (4 - first_weekday) % 7 but careful if first_weekday > 4
    first = date(year, month, 1)
    # days until first Friday: (4 - weekday) mod 7
    wd = first.weekday()  # Mon=0
    delta = (4 - wd) % 7
    first_friday = first + timedelta(days=delta)
    return first_friday + timedelta(days=14)


def monday_of_iso_week_containing(d: date) -> date:
    """Monday of the week that contains ``d`` (Python weekday: Mon=0)."""
    return d - timedelta(days=d.weekday())


def is_opex_week(d: date) -> bool:
    """True if ``d`` is a Mon–Fri in the week that contains the third Friday of that month."""
    if d.weekday() >= 5:
        return False
    tf = third_friday(d.year, d.month)
    mon = monday_of_iso_week_containing(tf)
    return mon <= d <= mon + timedelta(days=4)


def is_calendar_month_end(d: date) -> bool:
    """True if ``d`` is the last calendar day of its month."""
    _, last_day = calendar.monthrange(d.year, d.month)
    return d.day == last_day


def is_quarter_end_calendar(d: date) -> bool:
    """True if ``d`` is month-end in March, June, September, or December."""
    return d.month in (3, 6, 9, 12) and is_calendar_month_end(d)


def is_trading_month_end_at_index(dates: Sequence[date], i: int) -> bool:
    """True if the bar at ``i`` is the last session in its calendar month among ``dates``.

    Requires a next bar on a later date in a different month; the final bar in the series
    is never flagged (may still be within-calendar-month without a following session).
    """
    if i < 0 or i + 1 >= len(dates):
        return False
    cur, nxt = dates[i], dates[i + 1]
    return nxt.month != cur.month or nxt.year != cur.year


def is_trading_quarter_end_at_index(dates: Sequence[date], i: int) -> bool:
    """Trading month-end in Mar/Jun/Sep/Dec."""
    if not is_trading_month_end_at_index(dates, i):
        return False
    return dates[i].month in (3, 6, 9, 12)


def s4_impossible_bucket_keys(
    *,
    include_month_end: bool,
    include_quarter_end: bool,
) -> frozenset[str]:
    """S4 labels that cannot occur when both month-end and quarter-end dimensions are enabled.

    Realized quarter-end implies month-end, so ``q=1`` with ``m=0`` never appears in labels.
    """
    if include_month_end and include_quarter_end:
        return frozenset({"cal_001", "cal_101"})
    return frozenset()


def s4_merit_skip_min_events_check(
    bucket_key: str,
    evaluable_count: int,
    *,
    include_month_end: bool,
    include_quarter_end: bool,
) -> bool:
    """Whether S4 merit checklist should not enforce ``merit_min_events`` for this bucket/horizon.

    Skips impossible labels and horizons with no evaluable returns (N/A for this sample).
    """
    if bucket_key in s4_impossible_bucket_keys(
        include_month_end=include_month_end,
        include_quarter_end=include_quarter_end,
    ):
        return True
    if evaluable_count == 0:
        return True
    return False


def s4_bucket_label(
    *,
    opex_week: bool,
    month_end: bool,
    quarter_end: bool,
    include_opex: bool,
    include_month_end: bool,
    include_quarter_end: bool,
) -> str:
    """Stable 3-bit bucket key ``cal_abc`` with a/b/c in {0,1} for enabled dimensions only.

    ``cal_000`` means no enabled calendar flag is active on that day (complement of
    "special" days in the union of OpEx week, month-end, quarter-end).

    Disabled dimensions are forced to ``0`` in the label so bucket keys stay in a fixed
    ``cal_000`` … ``cal_111`` namespace regardless of config.
    """
    o = int(include_opex and opex_week)
    m = int(include_month_end and month_end)
    q = int(include_quarter_end and quarter_end)
    return f"cal_{o}{m}{q}"
