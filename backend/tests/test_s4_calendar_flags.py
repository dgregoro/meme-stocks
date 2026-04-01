"""Pure calendar helpers for S4 (no DB)."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

import pytest

from backend.app.services.s4_calendar_flags import (
    is_calendar_month_end,
    is_opex_week,
    is_quarter_end_calendar,
    monday_of_iso_week_containing,
    s4_bucket_label,
    third_friday,
)


@pytest.mark.unit
def test_third_friday_jan_2024() -> None:
    tf = third_friday(2024, 1)
    assert tf.weekday() == 4
    assert tf == date(2024, 1, 19)


@pytest.mark.unit
def test_monday_of_iso_week() -> None:
    d = date(2024, 1, 17)
    assert monday_of_iso_week_containing(d) == date(2024, 1, 15)


@pytest.mark.unit
def test_is_opex_week_weekday_in_mo_containing_third_friday() -> None:
    tf = third_friday(2024, 3)
    mon = monday_of_iso_week_containing(tf)
    assert is_opex_week(mon) is True
    assert is_opex_week(mon + timedelta(days=4)) is True


@pytest.mark.unit
def test_is_opex_week_false_weekend() -> None:
    sat = date(2024, 3, 16)
    assert sat.weekday() == 5
    assert is_opex_week(sat) is False


@pytest.mark.unit
def test_calendar_month_end() -> None:
    _, last = calendar.monthrange(2024, 2)
    assert is_calendar_month_end(date(2024, 2, last)) is True
    assert is_calendar_month_end(date(2024, 2, last - 1)) is False


@pytest.mark.unit
def test_quarter_end_calendar() -> None:
    assert is_quarter_end_calendar(date(2024, 3, 31)) is True
    assert is_quarter_end_calendar(date(2024, 3, 30)) is False


@pytest.mark.unit
def test_s4_bucket_label_disabled_dims_zero() -> None:
    assert (
        s4_bucket_label(
            opex_week=True,
            month_end=True,
            quarter_end=True,
            include_opex=False,
            include_month_end=True,
            include_quarter_end=True,
        )
        == "cal_011"
    )


@pytest.mark.unit
def test_s4_bucket_label_all_enabled() -> None:
    assert (
        s4_bucket_label(
            opex_week=True,
            month_end=False,
            quarter_end=False,
            include_opex=True,
            include_month_end=True,
            include_quarter_end=True,
        )
        == "cal_100"
    )
