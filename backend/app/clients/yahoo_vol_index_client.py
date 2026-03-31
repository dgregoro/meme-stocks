"""Yahoo Finance client for VIX / VIX3M daily closes (dedicated client with retries).

All Yahoo access for macro vol indices used by S3 goes through this module.
"""

from __future__ import annotations

from datetime import date, timedelta

import backoff
import pandas as pd
import yfinance as yf

from backend.app.utils.errors import ExternalAPIError


class YahooVolIndexClient:
    """Fetch aligned daily closes for ^VIX and ^VIX3M over [start, end] inclusive."""

    @staticmethod
    @backoff.on_exception(
        backoff.expo,
        Exception,
        max_time=45,
        jitter=backoff.full_jitter,
    )
    def _history_frame(ticker: yf.Ticker, start: date, end: date) -> pd.DataFrame:
        # yfinance end is exclusive — extend by one calendar day
        return ticker.history(start=start, end=end + timedelta(days=1))

    def fetch_vix_vix3m_closes(
        self,
        start: date,
        end: date,
        *,
        vix_symbol: str,
        vix3m_symbol: str,
    ) -> list[tuple[date, float, float]]:
        if start > end:
            return []
        try:
            t_vix = yf.Ticker(vix_symbol)
            t_3m = yf.Ticker(vix3m_symbol)
            h1 = self._history_frame(t_vix, start, end)
            h2 = self._history_frame(t_3m, start, end)
        except Exception as exc:  # pragma: no cover - network
            raise ExternalAPIError(f"Failed to fetch Yahoo history for {vix_symbol} / {vix3m_symbol}") from exc

        if h1.empty or h2.empty:
            return []

        def _close_series(df: pd.DataFrame) -> pd.Series:
            if "Close" not in df.columns:
                raise ExternalAPIError("Yahoo vol index response missing Close column")
            return df["Close"]

        def _closes_by_calendar_day(frame: pd.DataFrame) -> dict[date, float]:
            """Map UTC calendar date -> close; Yahoo often returns tz-aware indices that differ per symbol."""
            s = _close_series(frame)
            by_day: dict[date, float] = {}
            for idx, raw in s.items():
                ts = pd.Timestamp(idx)
                cal = ts.tz_convert("UTC").date() if ts.tzinfo is not None else ts.date()
                try:
                    by_day[cal] = float(raw)
                except (TypeError, ValueError) as exc:
                    raise ExternalAPIError(f"Malformed Yahoo close for vol index on {cal}") from exc
            return by_day

        d1 = _closes_by_calendar_day(h1)
        d2 = _closes_by_calendar_day(h2)
        out: list[tuple[date, float, float]] = []
        for cal in sorted(set(d1) & set(d2)):
            v, w = d1[cal], d2[cal]
            if v > 0 and w > 0:
                out.append((cal, v, w))
        return out
