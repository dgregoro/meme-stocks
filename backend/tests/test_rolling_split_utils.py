"""Unit tests for calendar-month rolling splits."""

from __future__ import annotations

from datetime import date

import pytest

from backend.app.services.rolling_split_utils import (
    RollingSplitValidationError,
    add_months,
    generate_monthly_rolling_splits,
)


def test_add_months_clamps_to_month_end() -> None:
    assert add_months(date(2020, 1, 31), 1) == date(2020, 2, 29)
    assert add_months(date(2019, 1, 31), 1) == date(2019, 2, 28)


def test_generate_splits_non_overlapping_contiguous() -> None:
    from datetime import timedelta

    splits = generate_monthly_rolling_splits(
        date(2024, 1, 1),
        date(2026, 1, 1),
        train_months=6,
        validate_months=2,
        test_months=None,
        step_months=3,
    )
    assert len(splits) >= 2
    assert splits[0].split_index == 0
    assert splits[0].train_start == date(2024, 1, 1)
    assert splits[0].train_end + timedelta(days=1) == splits[0].validate_start


def test_generate_splits_with_optional_test() -> None:
    from datetime import timedelta

    splits = generate_monthly_rolling_splits(
        date(2024, 1, 1),
        date(2026, 12, 31),
        train_months=3,
        validate_months=1,
        test_months=1,
        step_months=6,
    )
    for s in splits:
        assert s.test_start is not None and s.test_end is not None
        assert s.validate_end + timedelta(days=1) == s.test_start


def test_no_split_fits_raises() -> None:
    with pytest.raises(RollingSplitValidationError, match="No complete rolling split"):
        generate_monthly_rolling_splits(
            date(2024, 1, 1),
            date(2024, 1, 31),
            train_months=6,
            validate_months=2,
            test_months=None,
            step_months=1,
        )


def test_overall_order_validated() -> None:
    with pytest.raises(RollingSplitValidationError):
        generate_monthly_rolling_splits(
            date(2025, 1, 1),
            date(2024, 1, 1),
            train_months=2,
            validate_months=1,
            test_months=None,
            step_months=1,
        )
