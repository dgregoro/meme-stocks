"""S4 calendar / scheduled-event flags (US equity research skeleton).

Uses **calendar** conventions only (no exchange holiday calendar dependency):
- **Month-end**: last **calendar** day of the month (not necessarily last trading day).
- **Quarter-end**: month-end in Mar/Jun/Sep/Dec.
- **OpEx week**: Monday–Friday week containing the **third Friday** (standard
  monthly US equity options expiry pattern).

All functions are pure; enable/disable dimensions via caller (from config).
"""

from __future__ import annotations

import calendar
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

    Disabled dimensions are forced to ``0`` in the label so bucket keys stay in a fixed
    ``cal_000`` … ``cal_111`` namespace regardless of config.
    """
    o = int(include_opex and opex_week)
    m = int(include_month_end and month_end)
    q = int(include_quarter_end and quarter_end)
    return f"cal_{o}{m}{q}"
