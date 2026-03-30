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

        s1 = _close_series(h1)
        s2 = _close_series(h2)
        common = s1.index.intersection(s2.index)
        out: list[tuple[date, float, float]] = []
        for idx in common:
            ts = pd.Timestamp(idx)
            d = ts.date()
            try:
                v = float(s1.loc[idx])
                w = float(s2.loc[idx])
            except (TypeError, ValueError) as exc:
                raise ExternalAPIError(f"Malformed Yahoo close for vol index on {d}") from exc
            if v > 0 and w > 0:
                out.append((d, v, w))
        out.sort(key=lambda t: t[0])
        return out
