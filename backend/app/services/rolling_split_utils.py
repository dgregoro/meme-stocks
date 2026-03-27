"""Rolling chronological splits (calendar-month MVP) for robustness evaluation."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from backend.app.services.leader_follower_walk_forward_service import validate_walk_forward_windows


class RollingSplitValidationError(ValueError):
    """Invalid overall range, window lengths, or step."""


@dataclass(frozen=True)
class RollingSplitWindows:
    """One train → validate → (optional) test partition."""

    split_index: int
    train_start: date
    train_end: date
    validate_start: date
    validate_end: date
    test_start: date | None
    test_end: date | None


def add_months(d: date, n: int) -> date:
    """Add calendar months; day clamped to last day of target month."""
    if n < 0:
        raise RollingSplitValidationError("add_months only supports non-negative n")
    m0 = d.month - 1 + n
    y = d.year + m0 // 12
    mo = m0 % 12 + 1
    last = calendar.monthrange(y, mo)[1]
    day = min(d.day, last)
    return date(y, mo, day)


def _inclusive_end_after_months(start: date, months: int) -> date:
    if months < 1:
        raise RollingSplitValidationError("window length in months must be >= 1")
    return add_months(start, months) - timedelta(days=1)


def generate_monthly_rolling_splits(
    overall_start: date,
    overall_end: date,
    *,
    train_months: int,
    validate_months: int,
    test_months: int | None,
    step_months: int,
) -> list[RollingSplitWindows]:
    """Generate non-overlapping splits; each fully contained in [overall_start, overall_end].

    * Anchor starts at ``overall_start`` and advances by ``step_months`` after each accepted split.
    * Last day of train/validate/test uses calendar month arithmetic (see ``research.md``).
    * ``split_index`` is 0-based.
    """
    if overall_start > overall_end:
        raise RollingSplitValidationError("overall_start must be <= overall_end")
    if step_months < 1:
        raise RollingSplitValidationError("step_months must be >= 1")
    if train_months < 1 or validate_months < 1:
        raise RollingSplitValidationError("train_months and validate_months must be >= 1")
    if test_months is not None and test_months < 1:
        raise RollingSplitValidationError("test_months must be >= 1 when provided")

    splits: list[RollingSplitWindows] = []
    anchor = overall_start
    idx = 0

    while anchor <= overall_end:
        train_start = anchor
        train_end = _inclusive_end_after_months(train_start, train_months)
        validate_start = train_end + timedelta(days=1)
        validate_end = _inclusive_end_after_months(validate_start, validate_months)
        test_start: date | None
        test_end: date | None
        if test_months is not None:
            test_start = validate_end + timedelta(days=1)
            test_end = _inclusive_end_after_months(test_start, test_months)
        else:
            test_start = None
            test_end = None

        last_end = test_end if test_end is not None else validate_end
        if last_end > overall_end:
            break

        if train_start < overall_start:
            break

        validate_walk_forward_windows(
            train_start,
            train_end,
            validate_start,
            validate_end,
            test_start,
            test_end,
        )

        splits.append(
            RollingSplitWindows(
                split_index=idx,
                train_start=train_start,
                train_end=train_end,
                validate_start=validate_start,
                validate_end=validate_end,
                test_start=test_start,
                test_end=test_end,
            )
        )
        idx += 1
        anchor = add_months(anchor, step_months)

    if not splits:
        raise RollingSplitValidationError(
            "No complete rolling split fits in [overall_start, overall_end]; "
            "widen the range or shorten train/validate/test windows."
        )
    return splits
