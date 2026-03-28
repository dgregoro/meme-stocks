"""Shared datetime utilities for timezone normalization."""

from __future__ import annotations

from datetime import datetime, timezone


def ensure_utc_aware(dt: datetime | None) -> datetime | None:
    """Normalize datetime to UTC-aware; treat naive as UTC.

    Use before comparing datetimes from DB (which may be naive with SQLite)
    with datetime.now(timezone.utc).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
