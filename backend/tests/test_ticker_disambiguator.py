"""Unit tests for TickerDisambiguator."""

from __future__ import annotations

import pytest

from backend.app.utils.ticker_disambiguator import (
    DEFAULT_HIGH_COLLISION_TICKERS,
    TickerDisambiguator,
)


@pytest.mark.unit
class TestTickerDisambiguator:
    """Unit tests for TickerDisambiguator classification."""

    def test_cashtag_always_ticker(self) -> None:
        """Cashtag yields ticker regardless of high-collision."""
        d = TickerDisambiguator(valid_tickers=set(), high_collision_tickers={"RUN"})
        r = d.classify("I love $RUN", "RUN")
        assert r["label"] == "ticker"
        assert "cashtag" in r["reasons"]

    def test_ambiguous_word_no_context_excluded(self) -> None:
        """RUN without finance context is word when in high-collision."""
        d = TickerDisambiguator(valid_tickers={"RUN"}, high_collision_tickers={"RUN"})
        r = d.classify("I love to run every day", "RUN")
        assert r["label"] == "word"

    def test_it_word_no_context(self) -> None:
        """IT in 'it is what it is' is word."""
        d = TickerDisambiguator(valid_tickers=set(), high_collision_tickers={"IT"})
        r = d.classify("it is what it is", "IT")
        assert r["label"] == "word"

    def test_all_word_no_context(self) -> None:
        """ALL in 'all of you are crazy' is word."""
        d = TickerDisambiguator(valid_tickers=set(), high_collision_tickers={"ALL"})
        r = d.classify("all of you are crazy", "ALL")
        assert r["label"] == "word"

    def test_finance_context_promotes_ticker(self) -> None:
        """RUN with earnings in context is ticker when in universe."""
        d = TickerDisambiguator(valid_tickers={"RUN"}, high_collision_tickers={"RUN"})
        r = d.classify("RUN earnings tomorrow", "RUN")
        assert r["label"] == "ticker"
        assert r["score"] >= 3

    def test_open_calls_ticker(self) -> None:
        """OPEN with 'calls' in context is ticker when in universe."""
        d = TickerDisambiguator(valid_tickers={"OPEN"}, high_collision_tickers={"OPEN"})
        r = d.classify("OPEN calls are expensive", "OPEN")
        assert r["label"] == "ticker"

    def test_co_mention_helps(self) -> None:
        """NVDA and RUN together (ticker list) promotes RUN."""
        d = TickerDisambiguator(
            valid_tickers={"RUN", "NVDA"},
            high_collision_tickers={"RUN"},
        )
        r = d.classify("NVDA and RUN both look good", "RUN")
        assert r["label"] == "ticker"
        assert "ticker_list" in r["reasons"]

    def test_high_collision_not_in_universe_word(self) -> None:
        """High-collision symbol not in valid_tickers is always word (no hard evidence)."""
        d = TickerDisambiguator(valid_tickers={"AAPL"}, high_collision_tickers={"ON"})
        r = d.classify("ON the table", "ON")
        assert r["label"] == "word"

    def test_non_high_collision_kept_with_low_score(self) -> None:
        """Non high-collision symbol with score 0 is still ticker (permissive)."""
        d = TickerDisambiguator(valid_tickers={"AAPL"}, high_collision_tickers=set())
        r = d.classify("AAPL mentioned", "AAPL")
        assert r["label"] == "ticker"

    def test_classify_many_returns_one_per_candidate(self) -> None:
        """classify_many returns one result per candidate."""
        d = TickerDisambiguator(valid_tickers={"RUN", "NVDA"}, high_collision_tickers={"RUN"})
        results = d.classify_many("$RUN and NVDA", {"RUN", "NVDA"})
        assert len(results) == 2
        labels = {r["candidate"]: r["label"] for r in results}
        assert labels["RUN"] == "ticker"
        assert labels["NVDA"] == "ticker"

    def test_default_high_collision_includes_common_words(self) -> None:
        """DEFAULT_HIGH_COLLISION_TICKERS includes A, IT, ON, etc."""
        assert "A" in DEFAULT_HIGH_COLLISION_TICKERS
        assert "IT" in DEFAULT_HIGH_COLLISION_TICKERS
        assert "ON" in DEFAULT_HIGH_COLLISION_TICKERS
        assert "RUN" in DEFAULT_HIGH_COLLISION_TICKERS
