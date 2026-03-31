"""Tests for datetime_utils."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from zoneinfo import ZoneInfo

from backend.app.utils.datetime_utils import ensure_utc_aware


@pytest.mark.unit
def test_ensure_utc_aware_none() -> None:
    assert ensure_utc_aware(None) is None


@pytest.mark.unit
def test_ensure_utc_aware_naive_becomes_utc() -> None:
    dt = datetime(2024, 1, 2, 12, 0, 0)
    u = ensure_utc_aware(dt)
    assert u is not None
    assert u.tzinfo == timezone.utc


@pytest.mark.unit
def test_ensure_utc_aware_other_zone_converted() -> None:
    dt = datetime(2024, 1, 2, 12, 0, 0, tzinfo=ZoneInfo("America/New_York"))
    u = ensure_utc_aware(dt)
    assert u is not None
    assert u.tzinfo == timezone.utc
    assert u.hour != 12 or u.minute == 0
