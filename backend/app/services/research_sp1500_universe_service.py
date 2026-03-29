"""S&P Composite 1500 research universe: constituents + market-cap filter (Yahoo / yfinance).

Official index membership is licensed (S&P Dow Jones). Wikipedia tables are **unofficial**
reconstructions suitable for exploratory research only; prefer a vendor snapshot for production
rigor. Market cap is taken from Yahoo Finance via yfinance (alignment with your chosen as-of date
is approximate — see CLI help).
"""

from __future__ import annotations

import csv
import io
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import pandas as pd
import requests
import yfinance as yf

from backend.app.utils.errors import ExternalAPIError

logger = logging.getLogger(__name__)

WIKI_SP500 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
WIKI_SP400 = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"
WIKI_SP600 = "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"

_HTTP_HEADERS = {
    "User-Agent": "MemeStocksResearch/1.0 (research universe; contact per SEC best practice)",
}


def yahoo_ticker_symbol(raw: str) -> str:
    """Normalize tickers for Yahoo: uppercase, class dots to hyphen (BRK.B -> BRK-B)."""
    return raw.strip().upper().replace(".", "-")


def load_constituents_csv(path: Path) -> list[str]:
    """Load one ticker per row from CSV (column ``symbol`` or first column) or one ticker per line."""
    text = path.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        return []
    if path.suffix.lower() == ".csv":
        row1 = lines[0]
        if "," in row1 or row1.lower() in ("symbol", "ticker"):
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)
            if not rows:
                return []
            lower_keys = {k.lower() for k in rows[0]}
            if "symbol" in lower_keys:
                key = next(k for k in rows[0] if k.lower() == "symbol")
            elif "ticker" in lower_keys:
                key = next(k for k in rows[0] if k.lower() == "ticker")
            else:
                key = next(iter(rows[0].keys()))
            return [yahoo_ticker_symbol(str(r[key])) for r in rows if r.get(key)]
    return [yahoo_ticker_symbol(ln.split(",")[0]) for ln in lines]


def _table_symbols(df: pd.DataFrame) -> list[str]:
    for col in ("Symbol", "Ticker symbol", "Ticker"):
        if col in df.columns:
            return [yahoo_ticker_symbol(str(x)) for x in df[col].tolist() if pd.notna(x)]
    raise ValueError(f"No Symbol/Ticker column in Wikipedia table; columns={list(df.columns)}")


def fetch_sp_composite_1500_from_wikipedia(*, timeout_sec: int = 45) -> list[str]:
    """Download unofficial S&P 500+400+600 tables from Wikipedia and merge tickers.

    Not a substitute for licensed S&P constituent data. Wikipedia structure may change.
    """
    seen: dict[str, None] = {}
    out: list[str] = []
    for url in (WIKI_SP500, WIKI_SP400, WIKI_SP600):
        try:
            r = requests.get(url, headers=_HTTP_HEADERS, timeout=timeout_sec)
            r.raise_for_status()
        except requests.RequestException as exc:
            raise ExternalAPIError(f"Failed to fetch Wikipedia constituents: {url}") from exc
        try:
            tables = pd.read_html(io.StringIO(r.text))
        except ValueError as exc:
            raise ExternalAPIError(f"Could not parse HTML tables from {url}") from exc
        if not tables:
            raise ExternalAPIError(f"No tables found at {url}")
        syms = _table_symbols(tables[0])
        for s in syms:
            if s not in seen:
                seen[s] = None
                out.append(s)
    return out


def _market_cap_yahoo(symbol: str) -> float | None:
    """Best-effort market cap from yfinance (may be stale or missing)."""
    t = yf.Ticker(symbol)
    try:
        fi = t.fast_info
        mc_raw = fi.get("market_cap") if hasattr(fi, "get") else getattr(fi, "market_cap", None)
        if mc_raw is not None and float(mc_raw) > 0:
            return float(mc_raw)
    except Exception as exc:
        logger.warning("yfinance fast_info failed for %s: %s", symbol, exc)
    try:
        info = cast(dict[str, Any], t.info or {})
        mc = info.get("marketCap") or info.get("market_cap")
        if mc is not None and float(mc) > 0:
            return float(mc)
    except Exception as exc:
        logger.warning("yfinance info failed for %s: %s", symbol, exc)
    return None


@dataclass
class SP1500CapFilterResult:
    as_of: str
    max_market_cap_usd: float
    constituents_source: str
    included: list[str] = field(default_factory=list)
    excluded_over_cap: list[dict[str, Any]] = field(default_factory=list)
    excluded_no_cap: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "kind": "sp1500_cap_filter",
            "as_of": self.as_of,
            "max_market_cap_usd": self.max_market_cap_usd,
            "constituents_source": self.constituents_source,
            "n_included": len(self.included),
            "included": self.included,
            "excluded_over_cap": self.excluded_over_cap,
            "n_excluded_no_cap": len(self.excluded_no_cap),
            "excluded_no_cap": self.excluded_no_cap,
            "errors": self.errors,
        }


def filter_sp1500_by_market_cap(
    symbols: list[str],
    *,
    max_market_cap_usd: float,
    as_of_label: str,
    constituents_source: str,
    throttle_sec: float = 0.08,
) -> SP1500CapFilterResult:
    """Keep symbols whose Yahoo-reported market cap is below ``max_market_cap_usd``."""
    result = SP1500CapFilterResult(
        as_of=as_of_label,
        max_market_cap_usd=max_market_cap_usd,
        constituents_source=constituents_source,
    )
    cap_max = float(max_market_cap_usd)
    for sym in symbols:
        if not sym:
            continue
        try:
            mc = _market_cap_yahoo(sym)
        except Exception as exc:
            result.errors.append(f"{sym}: {exc}")
            result.excluded_no_cap.append(sym)
            time.sleep(throttle_sec)
            continue
        if mc is None:
            result.excluded_no_cap.append(sym)
            continue
        if mc >= cap_max:
            result.excluded_over_cap.append({"symbol": sym, "market_cap_usd": round(mc, 2)})
        else:
            result.included.append(sym)
        time.sleep(throttle_sec)
    return result
