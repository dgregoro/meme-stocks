"""Service for managing the symbol universe from NASDAQ and other exchanges."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, TypedDict

import requests
from sqlalchemy.orm import Session

from backend.app.data.repositories.symbol_universe_repo import SymbolUniverseRepository
from backend.app.models.symbol_universe import SymbolUniverse
from backend.app.utils.errors import ExternalAPIError

logger = logging.getLogger(__name__)

# NASDAQ Trader FTP site - public CSV files
NASDAQ_LISTINGS_URL = "https://www.nasdaq.com/api/v1/screener"
# Alternative: Direct NASDAQ FTP (requires parsing)
NASDAQ_FTP_CSV = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqlisted.txt"

# SEC EDGAR company tickers (comprehensive source)
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


class RefreshStats(TypedDict):
    """Return type for refresh_from_nasdaq statistics."""

    inserted: int
    updated: int
    total: int
    errors: list[str]


class SymbolUniverseService:
    """Service for fetching and managing stock symbol universe."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = SymbolUniverseRepository(db)

    def refresh_from_nasdaq(self) -> RefreshStats:
        """Refresh symbol universe from NASDAQ listings.

        Uses SEC EDGAR company tickers as the primary source (includes NASDAQ, NYSE, etc.)

        Returns:
            Dictionary with statistics: {'inserted': int, 'updated': int, 'total': int, 'errors': list}
        """
        stats: RefreshStats = {"inserted": 0, "updated": 0, "total": 0, "errors": []}

        try:
            # Use SEC EDGAR as primary source (includes all US exchanges)
            sec_symbols = self._fetch_sec_company_tickers()
            logger.info(f"Fetched {len(sec_symbols)} symbols from SEC EDGAR")

            for symbol_data in sec_symbols:
                try:
                    symbol = SymbolUniverse(
                        symbol=symbol_data["symbol"],
                        name=symbol_data.get("name"),
                        exchange=symbol_data.get("exchange", "NASDAQ"),  # Default to NASDAQ
                        is_etf=symbol_data.get("is_etf", False),
                        is_active=True,
                        sector=symbol_data.get("sector"),
                        industry=symbol_data.get("industry"),
                        last_seen=datetime.now(timezone.utc),
                    )

                    existing = self._repo.get(symbol.symbol)
                    if existing:
                        # Update existing
                        existing.name = symbol.name
                        existing.exchange = symbol.exchange
                        existing.is_etf = symbol.is_etf
                        existing.is_active = symbol.is_active
                        existing.sector = symbol.sector
                        existing.industry = symbol.industry
                        existing.last_seen = symbol.last_seen
                        existing.updated_at = datetime.now(timezone.utc)
                        stats["updated"] += 1
                    else:
                        # Insert new
                        self._repo.add(symbol)
                        stats["inserted"] += 1

                except Exception as exc:
                    logger.warning(f"Failed to process symbol {symbol_data.get('symbol')}: {exc}")
                    stats["errors"].append(str(exc))
                    continue

            self._db.commit()
            stats["total"] = stats["inserted"] + stats["updated"]
            logger.info(
                f"Symbol universe refresh complete: {stats['inserted']} inserted, "
                f"{stats['updated']} updated, {stats['total']} total"
            )

        except Exception as exc:
            logger.error(f"Error refreshing symbol universe: {exc}")
            self._db.rollback()
            raise ExternalAPIError(f"Failed to refresh symbol universe: {exc}") from exc

        return stats

    def _fetch_sec_company_tickers(self) -> list[dict[str, Any]]:
        """Fetch company tickers from SEC EDGAR.

        Returns:
            List of symbol dictionaries with symbol, name, exchange info
        """
        try:
            headers = {
                "User-Agent": "MemeStocksApp/1.0 (contact@example.com)",  # SEC requires user agent
            }
            response = requests.get(SEC_COMPANY_TICKERS_URL, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            symbols = []

            # SEC data format: {"0": {"cik_str": 123, "ticker": "AAPL", "title": "Apple Inc."}, ...}
            for key, company in data.items():
                ticker = company.get("ticker", "").strip().upper()
                if not ticker or len(ticker) > 5:
                    continue

                symbols.append(
                    {
                        "symbol": ticker,
                        "name": company.get("title", ""),
                        "exchange": None,  # SEC doesn't provide exchange
                        "is_etf": False,  # Would need additional source to determine
                        "sector": None,
                        "industry": None,
                    }
                )

            logger.info(f"Parsed {len(symbols)} symbols from SEC EDGAR")
            return symbols

        except requests.RequestException as exc:
            logger.error(f"Failed to fetch SEC company tickers: {exc}")
            raise ExternalAPIError(f"SEC API request failed: {exc}") from exc
        except (KeyError, ValueError) as exc:
            logger.error(f"Failed to parse SEC company tickers: {exc}")
            raise ExternalAPIError(f"Failed to parse SEC data: {exc}") from exc

    def get_symbols_set(self, active_only: bool = True) -> set[str]:
        """Get a set of all symbol strings for fast lookup.

        Args:
            active_only: Whether to only include active symbols

        Returns:
            Set of uppercase symbol strings
        """
        return self._repo.get_symbols_set(active_only=active_only)

    def count(self, active_only: bool = True) -> int:
        """Count symbols in the universe.

        Args:
            active_only: Whether to only count active symbols

        Returns:
            Total count of symbols
        """
        return self._repo.count(active_only=active_only)
