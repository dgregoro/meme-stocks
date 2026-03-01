from __future__ import annotations

import logging
import re
from typing import Set

logger = logging.getLogger(__name__)

# Common stock ticker pattern: 1-5 uppercase letters, possibly with $ prefix
TICKER_PATTERN = re.compile(r"\$?([A-Z]{1,5})\b")

# Tokens for context scoring (symbol + surrounding window)
TOKEN_PATTERN = re.compile(r"\b[\w\.\$:%+-]+\b")

# Symbols that are common words; require stronger evidence (hard evidence or score >= STRONG_THRESHOLD)
DANGEROUS_SYMBOLS: Set[str] = {
    "A",
    "I",
    "AM",
    "AN",
    "AS",
    "AT",
    "BE",
    "BY",
    "DO",
    "GO",
    "HE",
    "IF",
    "IN",
    "IS",
    "IT",
    "ME",
    "MY",
    "NO",
    "OF",
    "ON",
    "OR",
    "SO",
    "TO",
    "UP",
    "US",
    "WE",
    "THE",
    "AND",
    "FOR",
    "ARE",
    "BUT",
    "NOT",
    "YOU",
    "ALL",
    "CAN",
    "HER",
    "WAS",
    "ONE",
    "OUR",
    "OUT",
    "DAY",
    "GET",
    "HAS",
    "HIM",
    "HIS",
    "HOW",
    "ITS",
    "MAY",
    "NEW",
    "NOW",
    "OLD",
    "SEE",
    "TWO",
    "WHO",
    "WAY",
    "USE",
    "MAN",
    "YEAR",
    "LOVE",
    "ALSO",
    "SHE",
    "THEY",
    "THEM",
    "THIS",
    "THAT",
    "THESE",
    "THOSE",
    "MOON",
    "MOONS",
    "BUY",
    "SELL",
    "HOLD",
    "DD",
    "YOLO",
    "WSB",
    "ETF",
    "IPO",
    "AI",  # common word; keep only with market context (e.g. "AI up 3%")
}

# Backward compatibility alias
COMMON_WORDS = DANGEROUS_SYMBOLS

NORMAL_THRESHOLD = 1
STRONG_THRESHOLD = 3
CONTEXT_WINDOW = 10

# Finance keywords that suggest ticker context (lowercase for matching)
_FINANCE_KEYWORDS = frozenset(
    {
        "calls",
        "puts",
        "option",
        "strike",
        "expiry",
        "iv",
        "shares",
        "float",
        "market",
        "cap",
        "earnings",
        "guidance",
        "eps",
        "buy",
        "sell",
        "long",
        "short",
        "pt",
        "target",
        "price",
        "stock",
        "trading",
        "volume",
    }
)

# Price/percent pattern: +3%, -2.1%, $123, 123.45
_PRICE_PERCENT_PATTERN = re.compile(r"(\$?\d+\.?\d*%?|[\+\-]\d+\.?\d*%?)")

# Cache for symbol universe to avoid repeated DB queries
_symbol_universe_cache: Set[str] | None = None


def _score_symbol_context(text_original: str, symbol: str) -> tuple[int, list[str]]:
    """Score how much the surrounding context suggests symbol is used as a ticker.

    Uses cheap regex/keyword checks. Hard evidence (cashtag, exchange prefix)
    produces a high score and a reason so the caller can short-circuit keep.

    Args:
        text_original: Original text (preserve case for $ and exchange prefixes).
        symbol: Uppercase symbol to look for.

    Returns:
        (score, list of reason strings for debugging/metrics).
    """
    reasons: list[str] = []
    score = 0
    text_upper = text_original.upper()

    # Hard evidence: $SYMBOL or EXCHANGE:SYMBOL
    if re.search(r"\$" + re.escape(symbol) + r"\b", text_original):
        reasons.append("cashtag")
        score += 100
    for exchange in ("NYSE", "NASDAQ", "AMEX"):
        if re.search(re.escape(exchange) + r":" + re.escape(symbol) + r"\b", text_upper):
            reasons.append(f"exchange:{exchange}")
            score += 100

    if score >= 100:
        return (score, reasons)

    # Tokenize and find symbol positions
    tokens = TOKEN_PATTERN.findall(text_upper)
    symbol_upper = symbol.upper()
    indices = [i for i, t in enumerate(tokens) if t == symbol_upper or t == symbol]

    for idx in indices:
        start = max(0, idx - CONTEXT_WINDOW)
        end = min(len(tokens), idx + CONTEXT_WINDOW + 1)
        window = tokens[start:end]
        window_str = " ".join(window)

        # Price/percent near symbol
        if _PRICE_PERCENT_PATTERN.search(window_str):
            score += 3
            reasons.append("price_or_percent")
        # Finance keywords in window
        for kw in _FINANCE_KEYWORDS:
            if kw.upper() in window_str:
                score += 1
                reasons.append(f"finance_kw:{kw}")
                break
        # Ticker list: multiple other ticker-like tokens (exclude symbol and common words)
        ticker_like = [
            t for t in window if re.match(r"^[A-Z]{1,5}$", t) and t != symbol_upper and t not in DANGEROUS_SYMBOLS
        ]
        if len(ticker_like) >= 2:
            score += 3
            reasons.append("ticker_list")

    return (score, reasons)


def _has_hard_evidence(reasons: list[str]) -> bool:
    """True if reasons include cashtag or exchange prefix."""
    return any(r == "cashtag" or r.startswith("exchange:") for r in reasons)


def _should_keep_candidate(
    symbol: str,
    score: int,
    reasons: list[str],
    has_whitelist: bool,
) -> bool:
    """Apply dangerous-symbol policy: keep if evidence is strong enough."""
    is_dangerous = symbol in DANGEROUS_SYMBOLS
    if _has_hard_evidence(reasons):
        return True
    if is_dangerous:
        # In auto-discovery (no whitelist), require hard evidence only
        if not has_whitelist:
            return False
        return score >= STRONG_THRESHOLD
    # Non-dangerous: keep if score >= NORMAL_THRESHOLD or no negative context (score 0 = keep)
    return score >= NORMAL_THRESHOLD or score == 0


def load_symbol_universe_from_db() -> Set[str]:
    """Load symbol universe from database (cached).

    Returns:
        Set of valid stock symbols, or empty set if unavailable.
    """
    global _symbol_universe_cache

    if _symbol_universe_cache is not None:
        return _symbol_universe_cache

    try:
        from backend.app.data.database import SessionLocal
        from backend.app.data.repositories.symbol_universe_repo import SymbolUniverseRepository

        db = SessionLocal()
        try:
            repo = SymbolUniverseRepository(db)
            _symbol_universe_cache = repo.get_symbols_set(active_only=True)
            logger.debug(f"Loaded {len(_symbol_universe_cache)} symbols from universe")
            return _symbol_universe_cache
        finally:
            db.close()
    except Exception as exc:
        logger.warning(f"Failed to load symbol universe: {exc}")
        return set()


def clear_symbol_universe_cache() -> None:
    """Clear the symbol universe cache (call after refreshing universe)."""
    global _symbol_universe_cache
    _symbol_universe_cache = None


def _get_high_collision_set() -> set[str]:
    """Parse high-collision tickers from config (comma-separated)."""
    try:
        from backend.app.config import get_settings

        s = get_settings().ticker_high_collision_symbols or ""
        return {x.strip().upper() for x in s.split(",") if x.strip()}
    except Exception:
        return set()


def _log_maybe_audit(
    post_id: str | None,
    subreddit: str | None,
    text_preview: str,
    extracted: set[str],
    maybe_details: list[dict],
) -> None:
    """Log compact audit for maybe cases; no full post bodies."""
    for d in maybe_details:
        logger.info(
            "ticker_maybe candidate=%s label=%s score=%s reasons=%s post_id=%s subreddit=%s preview_len=%d extracted=%s",
            d.get("candidate"),
            d.get("label"),
            d.get("score"),
            d.get("reasons", [])[:3],
            post_id or "",
            subreddit or "",
            len(text_preview),
            sorted(extracted),
        )


def extract_tickers(
    text: str,
    known_symbols: Set[str] | None = None,
    use_symbol_universe: bool = True,
    subreddit: str | None = None,
    flair: str | None = None,
    *,
    debug: bool = False,
    _post_id: str | None = None,
) -> Set[str] | tuple[Set[str], list[dict]]:
    """Extract potential stock ticker symbols from text.

    Builds candidates from regex, optionally restricts to whitelist (known_symbols
    or symbol universe), then applies context scoring and dangerous-symbol policy
    so word-like tickers (e.g. ON, IT, A) are kept only with strong evidence.

    When ticker_disambiguation_enabled (config), uses TickerDisambiguator to
    classify each candidate as ticker/maybe/word; returns only ticker (and
    optionally maybe if ticker_disambiguation_return_maybe).

    Args:
        text: The text to search for tickers.
        known_symbols: Optional set of valid stock symbols to filter candidates.
        use_symbol_universe: If True and known_symbols is None, use DB symbol universe.
        subreddit: Optional subreddit name (for context / future use).
        flair: Optional post flair (for context / future use).
        debug: If True, return (tickers, list of per-candidate details).
        _post_id: Optional post id for audit logging (internal).

    Returns:
        Set of extracted ticker symbols (uppercase), or (set, details) when debug=True.
    """
    # Optional NER candidates (behind feature flag)
    ner_candidates: Set[str] = set()
    try:
        from backend.app.config import get_settings

        if get_settings().enable_ticker_ner:
            from backend.app.utils.ticker_ner import extract_ner_candidates

            ner_candidates = extract_ner_candidates(text)
    except Exception as exc:
        logger.debug("Optional NER candidates skipped: %s", exc)

    # Regex candidates
    matches = TICKER_PATTERN.findall(text.upper())
    candidates: Set[str] = {m for m in matches if len(m) >= 1}
    candidates |= ner_candidates

    # Determine whitelist (valid symbols universe)
    if known_symbols is not None:
        whitelist = known_symbols
    elif use_symbol_universe:
        whitelist = load_symbol_universe_from_db()
        if not whitelist:
            logger.debug("Symbol universe is empty, using auto-discovery mode")
            whitelist = set()
    else:
        whitelist = set()

    # If whitelist exists, restrict candidates early
    if whitelist:
        candidates = candidates & whitelist

    try:
        from backend.app.config import get_settings

        settings = get_settings()
        disambiguation_enabled = getattr(settings, "ticker_disambiguation_enabled", True)
    except Exception:
        disambiguation_enabled = True

    if disambiguation_enabled:
        # Use TickerDisambiguator with config
        from backend.app.utils.ticker_disambiguator import TickerDisambiguator

        try:
            _s = get_settings()
            return_maybe = getattr(_s, "ticker_disambiguation_return_maybe", False)
            window_tokens = getattr(_s, "ticker_disambiguation_window_tokens", 5)
        except Exception:
            return_maybe = False
            window_tokens = 5

        high_collision = _get_high_collision_set() | set(DANGEROUS_SYMBOLS)
        disambiguator = TickerDisambiguator(
            valid_tickers=whitelist,
            window_tokens=window_tokens,
            high_collision_tickers=high_collision,
        )
        results = disambiguator.classify_many(text, candidates, subreddit=subreddit, flair=flair)
        result: Set[str] = set()
        maybe_details: list[dict] = []
        for r in results:
            label = r["label"]
            if label == "ticker":
                result.add(r["candidate"])
            elif label == "maybe":
                maybe_details.append(dict(r))
                if return_maybe:
                    result.add(r["candidate"])
        if maybe_details and (debug or return_maybe):
            preview = (text[:80] + "…") if len(text) > 80 else text
            _log_maybe_audit(
                _post_id,
                subreddit,
                preview,
                result,
                maybe_details,
            )
        if debug:
            return (result, [dict(r) for r in results])
        return result

    # Legacy path: score + dangerous-symbol policy
    has_whitelist = len(whitelist) > 0
    result = set()
    details: list[dict] = []
    for symbol in candidates:
        score, reasons = _score_symbol_context(text, symbol)
        if _should_keep_candidate(symbol, score, reasons, has_whitelist):
            result.add(symbol)
        if debug:
            details.append(
                {
                    "candidate": symbol,
                    "label": "ticker" if symbol in result else "word",
                    "score": score,
                    "reasons": reasons,
                }
            )
    if debug:
        return (result, details)
    return result
