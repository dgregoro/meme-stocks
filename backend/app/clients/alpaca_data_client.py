"""Alpaca market data client with free-plan-safe end-time handling.

On the Alpaca free plan, full-market SIP is 15-minute delayed. Querying the last
~15 minutes can fail. This module provides a single authoritative helper so all
callers use a safe end time (now - safety_minutes) when free_plan_mode is True.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def compute_safe_end_time(
    now_utc: datetime,
    safety_minutes: int,
    free_plan_mode: bool = True,
) -> datetime:
    """Compute the latest end time for a data request that stays within plan limits.

    When free_plan_mode is True, we must not query the last ~15 minutes when
    using delayed SIP on the free plan—requests too close to "now" can fail.
    So we set end = now_utc - safety_minutes (e.g. 20 to be safely > 15).

    When free_plan_mode is False, we allow end = now_utc (no safety buffer).

    All timestamps are UTC; callers must pass timezone-aware now_utc.
    """
    if free_plan_mode:
        return now_utc - timedelta(minutes=safety_minutes)
    return now_utc


class AlpacaDataClient:
    """Client for Alpaca minute-bar data. Uses compute_safe_end_time for all requests."""

    def __init__(
        self,
        *,
        free_plan_mode: bool = True,
        end_time_safety_minutes: int = 20,
        feed: str = "delayed_sip",
    ) -> None:
        self._free_plan_mode = free_plan_mode
        self._end_time_safety_minutes = end_time_safety_minutes
        self._feed = feed

    def compute_safe_end_time(self, now_utc: datetime) -> datetime:
        """Return the safe end time for a request from this client's config."""
        return compute_safe_end_time(
            now_utc,
            self._end_time_safety_minutes,
            self._free_plan_mode,
        )

    def get_minute_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> list[dict]:
        """Fetch minute bars for symbol from start to end (both UTC).

        Callers must pass end <= compute_safe_end_time(now) when free_plan_mode
        is True; the ingestion service enforces this. This method does not
        clamp end so that the single source of truth for safe end is
        compute_safe_end_time.

        Returns a list of bar dicts (open, high, low, close, volume, timestamp).
        Implementation may be stubbed until Alpaca API integration is added.
        """
        # Placeholder: real implementation would call Alpaca API with self._feed.
        # Kept here so ingestion service can call one method; tests can mock it.
        _ = symbol
        _ = start
        _ = end
        return []
