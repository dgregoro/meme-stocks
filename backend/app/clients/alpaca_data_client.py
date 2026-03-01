"""Alpaca market data client with free-plan-safe end-time handling.

On the Alpaca free plan, full-market SIP is 15-minute delayed. Querying the last
~15 minutes can fail. This module provides a single authoritative helper so all
callers use a safe end time (now - safety_minutes) when free_plan_mode is True.
"""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timedelta
from typing import Any

import requests

from backend.app.utils.errors import ExternalAPIError

logger = logging.getLogger(__name__)

# Max retries for 429/5xx with exponential backoff
ALPACA_MAX_RETRIES = 6
ALPACA_BASE_DELAY = 1.0
ALPACA_MAX_DELAY = 120.0


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
        api_key_id: str | None = None,
        api_secret_key: str | None = None,
        base_url: str = "https://data.alpaca.markets",
    ) -> None:
        self._free_plan_mode = free_plan_mode
        self._end_time_safety_minutes = end_time_safety_minutes
        self._feed = feed
        self._api_key_id = api_key_id
        self._api_secret_key = api_secret_key
        self._base_url = base_url.rstrip("/")

    def compute_safe_end_time(self, now_utc: datetime) -> datetime:
        """Return the safe end time for a request from this client's config."""
        return compute_safe_end_time(
            now_utc,
            self._end_time_safety_minutes,
            self._free_plan_mode,
        )

    def _effective_end(self, end: datetime, now_utc: datetime) -> datetime:
        """When free_plan_mode, clamp end to safe end so callers cannot bypass."""
        if not self._free_plan_mode:
            return end
        safe = self.compute_safe_end_time(now_utc)
        return min(end, safe)

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
        bars_dict, _ = self.fetch_bars_page(
            symbols=[symbol],
            start=start,
            end=end,
            timeframe="1Min",
            feed=self._feed,
            page_token=None,
        )
        return bars_dict.get(symbol, [])

    def fetch_bars_page(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        timeframe: str = "1Min",
        feed: str | None = None,
        page_token: str | None = None,
        limit: int = 10000,
    ) -> tuple[dict[str, list[dict]], str | None]:
        """Fetch one page of multi-symbol bars. Returns (bars_by_symbol, next_page_token).

        When free_plan_mode is True, end is clamped to compute_safe_end_time(now)
        so callers cannot bypass the safe window.
        """
        from datetime import timezone

        feed = feed or self._feed
        now_utc = datetime.now(timezone.utc)
        end = self._effective_end(end, now_utc)

        if not symbols:
            return {}, None

        url = f"{self._base_url}/v2/stocks/bars"
        params: dict[str, Any] = {
            "symbols": ",".join(symbols),
            "timeframe": timeframe,
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
            "limit": limit,
            "feed": feed,
        }
        if page_token:
            params["page_token"] = page_token

        headers: dict[str, str] = {}
        if self._api_key_id and self._api_secret_key:
            headers["APCA-API-KEY-ID"] = self._api_key_id
            headers["APCA-API-SECRET-KEY"] = self._api_secret_key

        last_exc: Exception | None = None
        for attempt in range(ALPACA_MAX_RETRIES):
            try:
                resp = requests.get(url, params=params, headers=headers or None, timeout=60)
                if resp.status_code == 200:
                    data = resp.json()
                    bars = data.get("bars", {})
                    next_token = data.get("next_page_token")
                    return bars, next_token if next_token else None
                if resp.status_code == 429:
                    last_exc = ExternalAPIError(f"Alpaca rate limited (429); body={resp.text[:500]}")
                elif 500 <= resp.status_code < 600:
                    last_exc = ExternalAPIError(f"Alpaca server error {resp.status_code}; body={resp.text[:500]}")
                else:
                    raise ExternalAPIError(f"Alpaca bars request failed: {resp.status_code} body={resp.text[:500]}")
            except requests.RequestException as e:
                last_exc = ExternalAPIError(f"Alpaca request failed: {e}")

            if attempt < ALPACA_MAX_RETRIES - 1:
                delay = min(
                    ALPACA_BASE_DELAY * (2**attempt) + random.uniform(0, 1),
                    ALPACA_MAX_DELAY,
                )
                logger.warning(
                    "Alpaca bars request failed (attempt %s/%s), retrying in %.1fs: %s",
                    attempt + 1,
                    ALPACA_MAX_RETRIES,
                    delay,
                    last_exc,
                )
                time.sleep(delay)

        if last_exc:
            raise last_exc
        raise ExternalAPIError("Alpaca bars request failed after retries")
