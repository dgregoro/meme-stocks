from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import List, Optional

import pandas as pd
import yfinance as yf
import backoff

from backend.app.utils.errors import ExternalAPIError


@dataclass(frozen=True)
class PriceBar:
    """Normalized OHLCV price bar returned from Yahoo Finance."""

    stock_symbol: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    source_timestamp: datetime


class YahooFinanceService:
    """Service for fetching price data from Yahoo Finance via yfinance."""

    @staticmethod
    @backoff.on_exception(
        backoff.expo,
        Exception,  # yfinance raises various exceptions; we wrap into ExternalAPIError
        max_time=30,
        jitter=backoff.full_jitter,
    )
    def _safe_history(ticker: yf.Ticker, start: date, end: date) -> pd.DataFrame:
        return ticker.history(start=start, end=end)

    def fetch_historical_prices(self, symbol: str, start: date, end: date) -> List[PriceBar]:
        """Fetch historical OHLCV data for a symbol between start and end (inclusive).

        Raises ExternalAPIError on network or data issues instead of failing silently.
        """

        try:
            ticker = yf.Ticker(symbol)
            history: pd.DataFrame = self._safe_history(ticker, start=start, end=end)
        except Exception as exc:  # pragma: no cover - network/remote errors
            raise ExternalAPIError(f"Failed to fetch historical prices for {symbol}") from exc

        if history.empty:
            # Explicitly signal "no data" by returning an empty list; callers can decide
            # how to handle it (e.g. error vs. skip).
            return []

        results: list[PriceBar] = []
        for idx, row in history.iterrows():
            try:
                bar_date = idx.date()
                results.append(
                    PriceBar(
                        stock_symbol=symbol,
                        date=bar_date,
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=int(row["Volume"]),
                        source_timestamp=datetime.now(timezone.utc),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ExternalAPIError(f"Malformed price data row for {symbol} on {idx}") from exc

        return results

    def fetch_latest_price(self, symbol: str) -> Optional[PriceBar]:
        """Fetch the most recent closing price for a symbol.

        Returns None if Yahoo does not return any data for the symbol.
        """

        today = date.today()
        # Ask for a short history window and take the last bar.
        history = self.fetch_historical_prices(symbol, start=today, end=today)
        if not history:
            return None

        return history[-1]
