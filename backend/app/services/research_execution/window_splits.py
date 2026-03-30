"""Shared calendar / trading-day window splitting for walk-forward style research.

Used by daily-frequency merit rolling and available for future generic backtests.
"""

from __future__ import annotations

from datetime import date, timedelta


def split_calendar_range(start: date, end: date, n: int) -> list[tuple[date, date]]:
    """Partition ``[start, end]`` inclusive into ``n`` contiguous calendar sub-ranges."""
    if n <= 1:
        return [(start, end)]
    if start > end:
        raise ValueError("start must be <= end")
    total_days = (end - start).days + 1
    if total_days < n:
        return [(start, end)]
    base, rem = divmod(total_days, n)
    out: list[tuple[date, date]] = []
    cur = start
    for i in range(n):
        seg_days = base + (1 if i < rem else 0)
        if seg_days <= 0:
            break
        seg_end = cur + timedelta(days=seg_days - 1)
        if seg_end > end:
            seg_end = end
        out.append((cur, seg_end))
        cur = seg_end + timedelta(days=1)
        if cur > end:
            break
    return out if out else [(start, end)]


def split_sorted_trading_days(sorted_days: list[date], n: int) -> list[tuple[date, date]]:
    """Partition sorted trading days into ``n`` contiguous index blocks; each block is [first, last] date."""
    if not sorted_days:
        return []
    if n <= 1:
        return [(sorted_days[0], sorted_days[-1])]
    L = len(sorted_days)
    base, rem = divmod(L, n)
    out: list[tuple[date, date]] = []
    idx = 0
    for i in range(n):
        take = base + (1 if i < rem else 0)
        if take <= 0:
            continue
        chunk = sorted_days[idx : idx + take]
        if chunk:
            out.append((chunk[0], chunk[-1]))
        idx += take
    return out if out else [(sorted_days[0], sorted_days[-1])]
