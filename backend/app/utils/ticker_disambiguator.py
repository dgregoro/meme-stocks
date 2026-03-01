"""Ticker vs common-word disambiguation with no external dependencies.

Classifies candidate tokens as ticker, maybe, or word using context scoring
and a configurable high-collision set. Strict policy: high-collision symbols
require hard evidence (cashtag/exchange) or score >= STRONG_THRESHOLD when
in the valid tickers universe.
"""

from __future__ import annotations

import re
from typing import TypedDict

# Default high-collision tickers (common words); can be overridden via config
DEFAULT_HIGH_COLLISION_TICKERS = frozenset(
    {
        "A",
        "IT",
        "OR",
        "ON",
        "ALL",
        "ONE",
        "RUN",
        "FOR",
        "LOVE",
        "OPEN",
        "REAL",
        "HOPE",
        "RIDE",
        "SAVE",
        "SOLO",
        "TALK",
        "WORK",
        "PLAN",
        "LIVE",
        "PLAY",
    }
)

# Token pattern for context window
_TOKEN_PATTERN = re.compile(r"\b[\w\.\$:%+-]+\b")

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
# Strong finance keywords: one occurrence in window is enough for STRONG_THRESHOLD
_STRONG_FINANCE_KEYWORDS = frozenset({"earnings", "calls", "puts", "strike", "shares", "price", "target"})

# Price/percent pattern
_PRICE_PERCENT_PATTERN = re.compile(r"(\$?\d+\.?\d*%?|[\+\-]\d+\.?\d*%?)")

NORMAL_THRESHOLD = 1
STRONG_THRESHOLD = 3


class DisambiguationResult(TypedDict):
    """Result of classifying a single candidate."""

    candidate: str
    label: str  # "ticker" | "maybe" | "word"
    score: int
    reasons: list[str]


def _score_context(
    text_original: str,
    symbol: str,
    window_tokens: int,
    valid_tickers: set[str] | None = None,
) -> tuple[int, list[str]]:
    """Score how much context suggests symbol is used as a ticker.

    Hard evidence (cashtag, exchange prefix) yields high score. Otherwise
    uses a sliding window for finance keywords, price/percent, and
    co-mentioned tickers (only tokens in valid_tickers count as ticker list).
    """
    reasons: list[str] = []
    score = 0
    text_upper = text_original.upper()
    symbol_upper = symbol.upper()

    # Hard evidence
    if re.search(r"\$" + re.escape(symbol) + r"\b", text_original):
        reasons.append("cashtag")
        score += 100
    for exchange in ("NYSE", "NASDAQ", "AMEX"):
        if re.search(re.escape(exchange) + r":" + re.escape(symbol) + r"\b", text_upper):
            reasons.append(f"exchange:{exchange}")
            score += 100

    if score >= 100:
        return (score, reasons)

    # Tokenize and score window around each occurrence
    tokens = _TOKEN_PATTERN.findall(text_upper)
    indices = [i for i, t in enumerate(tokens) if t == symbol_upper or t == symbol]
    valid = valid_tickers or set()

    for idx in indices:
        start = max(0, idx - window_tokens)
        end = min(len(tokens), idx + window_tokens + 1)
        window = tokens[start:end]
        window_str = " ".join(window)

        if _PRICE_PERCENT_PATTERN.search(window_str):
            score += 3
            reasons.append("price_or_percent")
        # Strong finance keyword (earnings, calls, etc.) gives enough for STRONG_THRESHOLD
        for kw in _STRONG_FINANCE_KEYWORDS:
            if kw.upper() in window_str:
                score += 3
                reasons.append(f"strong_finance_kw:{kw}")
                break
        else:
            for kw in _FINANCE_KEYWORDS:
                if kw.upper() in window_str:
                    score += 1
                    reasons.append(f"finance_kw:{kw}")
                    break
        # Ticker list: other tokens in window that are in valid_tickers (co-mention helps)
        ticker_like = [
            t for t in window if re.match(r"^[A-Z]{1,5}$", t) and t != symbol_upper and (not valid or t in valid)
        ]
        if len(ticker_like) >= 1:
            score += 3
            reasons.append("ticker_list")

    return (score, reasons)


def _has_hard_evidence(reasons: list[str]) -> bool:
    return any(r == "cashtag" or r.startswith("exchange:") for r in reasons)


class TickerDisambiguator:
    """Classifies candidate tokens as ticker, maybe, or word.

    Uses a strict policy for high-collision symbols: they require hard
    evidence or score >= STRONG_THRESHOLD when in the valid tickers set.
    """

    def __init__(
        self,
        valid_tickers: set[str],
        *,
        window_tokens: int = 5,
        high_collision_tickers: set[str] | frozenset[str] | None = None,
    ) -> None:
        self._valid = valid_tickers
        self._window_tokens = window_tokens
        self._high_collision = high_collision_tickers or DEFAULT_HIGH_COLLISION_TICKERS

    def classify(
        self,
        text: str,
        candidate: str,
        subreddit: str | None = None,
        flair: str | None = None,
    ) -> DisambiguationResult:
        """Classify a single candidate token.

        subreddit and flair are reserved for future use (e.g. finance
        subreddit or flair could boost score). Currently unused.

        Returns:
            Dict with candidate, label ("ticker"|"maybe"|"word"), score, reasons.
        """
        _ = subreddit, flair  # reserved
        score, reasons = _score_context(text, candidate, self._window_tokens, valid_tickers=self._valid)
        symbol_upper = candidate.upper()
        in_universe = symbol_upper in self._valid
        is_high_collision = symbol_upper in self._high_collision

        if _has_hard_evidence(reasons):
            return DisambiguationResult(
                candidate=symbol_upper,
                label="ticker",
                score=score,
                reasons=reasons,
            )

        if is_high_collision:
            if not in_universe:
                return DisambiguationResult(
                    candidate=symbol_upper,
                    label="word",
                    score=score,
                    reasons=reasons,
                )
            if score >= STRONG_THRESHOLD:
                return DisambiguationResult(
                    candidate=symbol_upper,
                    label="ticker",
                    score=score,
                    reasons=reasons,
                )
            if 0 < score < STRONG_THRESHOLD:
                return DisambiguationResult(
                    candidate=symbol_upper,
                    label="maybe",
                    score=score,
                    reasons=reasons,
                )
            return DisambiguationResult(
                candidate=symbol_upper,
                label="word",
                score=score,
                reasons=reasons,
            )

        # Not high-collision
        if score >= NORMAL_THRESHOLD or score == 0:
            return DisambiguationResult(
                candidate=symbol_upper,
                label="ticker",
                score=score,
                reasons=reasons,
            )
        return DisambiguationResult(
            candidate=symbol_upper,
            label="maybe" if score > 0 else "word",
            score=score,
            reasons=reasons,
        )

    def classify_many(
        self,
        text: str,
        candidates: set[str],
        subreddit: str | None = None,
        flair: str | None = None,
    ) -> list[DisambiguationResult]:
        """Classify multiple candidates. Returns one result per candidate."""
        return [self.classify(text, c, subreddit=subreddit, flair=flair) for c in candidates]
