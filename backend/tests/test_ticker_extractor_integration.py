"""Integration tests for ticker extraction with disambiguation."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.app.utils.ticker_extractor import (
    clear_symbol_universe_cache,
    extract_tickers,
    load_symbol_universe_from_db,
)


@pytest.mark.unit
def test_cashtag_always_wins() -> None:
    """I love $RUN should include RUN."""
    clear_symbol_universe_cache()
    with patch("backend.app.utils.ticker_extractor.load_symbol_universe_from_db", return_value=set()):
        # With disambiguation on, RUN is high-collision; cashtag forces ticker
        tickers = extract_tickers("I love $RUN", use_symbol_universe=False)
    assert "RUN" in tickers


@pytest.mark.unit
def test_ambiguous_run_excluded_without_finance_context() -> None:
    """I love to run every day should NOT include RUN."""
    clear_symbol_universe_cache()
    with patch("backend.app.utils.ticker_extractor.load_symbol_universe_from_db", return_value=set()):
        tickers = extract_tickers(
            "I love to run every day",
            known_symbols={"RUN"},
            use_symbol_universe=False,
        )
    assert "RUN" not in tickers


@pytest.mark.unit
def test_it_excluded_plain_sentence() -> None:
    """it is what it is should NOT include IT."""
    clear_symbol_universe_cache()
    with patch("backend.app.utils.ticker_extractor.load_symbol_universe_from_db", return_value=set()):
        tickers = extract_tickers("it is what it is", use_symbol_universe=False)
    assert "IT" not in tickers


@pytest.mark.unit
def test_all_excluded_plain_sentence() -> None:
    """all of you are crazy should NOT include ALL."""
    clear_symbol_universe_cache()
    with patch("backend.app.utils.ticker_extractor.load_symbol_universe_from_db", return_value=set()):
        tickers = extract_tickers(
            "all of you are crazy",
            known_symbols={"ALL"},
            use_symbol_universe=False,
        )
    assert "ALL" not in tickers


@pytest.mark.unit
def test_run_earnings_includes_run_when_in_universe() -> None:
    """RUN earnings tomorrow should include RUN if RUN is in tickers universe."""
    clear_symbol_universe_cache()
    with patch("backend.app.utils.ticker_extractor.load_symbol_universe_from_db", return_value={"RUN"}):
        tickers = extract_tickers(
            "RUN earnings tomorrow",
            use_symbol_universe=True,
        )
    assert "RUN" in tickers


@pytest.mark.unit
def test_open_calls_includes_open() -> None:
    """OPEN calls are expensive should include OPEN when in universe."""
    clear_symbol_universe_cache()
    with patch("backend.app.utils.ticker_extractor.load_symbol_universe_from_db", return_value={"OPEN"}):
        tickers = extract_tickers(
            "OPEN calls are expensive",
            use_symbol_universe=True,
        )
    assert "OPEN" in tickers


@pytest.mark.unit
def test_co_mention_includes_run() -> None:
    """NVDA and RUN both look good should include RUN when both in universe."""
    clear_symbol_universe_cache()
    with patch("backend.app.utils.ticker_extractor.load_symbol_universe_from_db", return_value={"RUN", "NVDA"}):
        tickers = extract_tickers(
            "NVDA and RUN both look good",
            use_symbol_universe=True,
        )
    assert "RUN" in tickers
    assert "NVDA" in tickers


@pytest.mark.unit
def test_dot_class_style_in_universe() -> None:
    """Universe containing BRK.B and AAPL: AAPL extracted; no crash with dot symbol."""
    clear_symbol_universe_cache()
    # TICKER_PATTERN matches 1-5 uppercase so "BRK.B" yields candidate "BRK" only; we don't
    # yet normalize BRK/B -> BRK.B. This test ensures universe with BRK.B doesn't break.
    with patch("backend.app.utils.ticker_extractor.load_symbol_universe_from_db", return_value={"BRK.B", "AAPL"}):
        tickers = extract_tickers("AAPL is great", use_symbol_universe=True)
    assert "AAPL" in tickers
    assert isinstance(tickers, set)


@pytest.mark.unit
def test_debug_returns_tuple() -> None:
    """When debug=True, extract_tickers returns (set, list of details)."""
    clear_symbol_universe_cache()
    with patch("backend.app.utils.ticker_extractor.load_symbol_universe_from_db", return_value={"AAPL"}):
        out = extract_tickers("I love AAPL", use_symbol_universe=True, debug=True)
    assert isinstance(out, tuple)
    tickers, details = out
    assert isinstance(tickers, set)
    assert "AAPL" in tickers
    assert isinstance(details, list)
    assert any(d.get("candidate") == "AAPL" and d.get("label") == "ticker" for d in details)


@pytest.mark.unit
def test_toggle_off_returns_old_behavior() -> None:
    """When ticker_disambiguation_enabled=False, use legacy scoring (same outcomes)."""
    clear_symbol_universe_cache()
    with patch("backend.app.utils.ticker_extractor.load_symbol_universe_from_db", return_value={"ON"}):
        with patch("backend.app.config.get_settings") as mock_get_settings:
            mock_settings = mock_get_settings.return_value
            mock_settings.ticker_disambiguation_enabled = False
            tickers_off = extract_tickers(
                "ON the table",
                use_symbol_universe=True,
            )
            mock_settings.ticker_disambiguation_enabled = True
            mock_settings.ticker_disambiguation_return_maybe = False
            mock_settings.ticker_disambiguation_window_tokens = 5
            mock_settings.ticker_high_collision_symbols = (
                "A,IT,OR,ON,ALL,ONE,RUN,FOR,LOVE,OPEN,REAL,HOPE,RIDE,SAVE,SOLO,TALK,WORK,PLAN,LIVE,PLAY"
            )
            tickers_on = extract_tickers(
                "ON the table",
                use_symbol_universe=True,
            )
    # Both should exclude ON in "ON the table"
    assert "ON" not in tickers_off
    assert "ON" not in tickers_on


@pytest.mark.unit
def test_legacy_path_exchange_prefix_keeps_symbol() -> None:
    """NYSE:/NASDAQ: prefix short-circuits dangerous-symbol policy (legacy scorer)."""
    clear_symbol_universe_cache()
    with patch("backend.app.utils.ticker_extractor.load_symbol_universe_from_db", return_value=set()):
        with patch("backend.app.config.get_settings") as mock_get_settings:
            mock_get_settings.return_value.ticker_disambiguation_enabled = False
            tickers = extract_tickers(
                "NASDAQ:ZM beats estimates",
                known_symbols={"ZM"},
                use_symbol_universe=False,
            )
    assert "ZM" in tickers


@pytest.mark.unit
def test_load_symbol_universe_from_db_session_failure_returns_empty() -> None:
    clear_symbol_universe_cache()
    with patch("backend.app.data.database.SessionLocal", side_effect=RuntimeError("db unavailable")):
        out = load_symbol_universe_from_db()
    assert out == set()
    clear_symbol_universe_cache()


@pytest.mark.unit
def test_extract_tickers_optional_ner_union(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_symbol_universe_cache()
    monkeypatch.setenv("ENABLE_TICKER_NER", "true")
    from backend.app.config import get_settings

    get_settings.cache_clear()
    try:
        with patch("backend.app.utils.ticker_extractor.load_symbol_universe_from_db", return_value={"PLTR"}):
            with patch("backend.app.utils.ticker_ner.extract_ner_candidates", return_value={"PLTR"}):
                tickers = extract_tickers("long PLTR", use_symbol_universe=True)
        assert "PLTR" in tickers
    finally:
        get_settings.cache_clear()
        clear_symbol_universe_cache()


@pytest.mark.unit
def test_legacy_path_finance_keyword_and_ticker_cluster() -> None:
    clear_symbol_universe_cache()
    with patch("backend.app.utils.ticker_extractor.load_symbol_universe_from_db", return_value=set()):
        with patch("backend.app.config.get_settings") as mock_get_settings:
            mock_get_settings.return_value.ticker_disambiguation_enabled = False
            result = extract_tickers(
                "NVDA AMD MSFT stock story with +2% move",
                known_symbols={"NVDA", "AMD", "MSFT"},
                use_symbol_universe=False,
            )
    assert isinstance(result, set)
    assert {"NVDA", "AMD", "MSFT"} <= result


@pytest.mark.unit
def test_legacy_debug_returns_scored_details() -> None:
    clear_symbol_universe_cache()
    with patch("backend.app.utils.ticker_extractor.load_symbol_universe_from_db", return_value=set()):
        with patch("backend.app.config.get_settings") as mock_get_settings:
            mock_get_settings.return_value.ticker_disambiguation_enabled = False
            out = extract_tickers(
                "AAPL up +3% today",
                known_symbols={"AAPL"},
                use_symbol_universe=False,
                debug=True,
            )
    assert isinstance(out, tuple)
    tickers, details = out
    assert "AAPL" in tickers
    assert any(isinstance(d, dict) and d.get("candidate") == "AAPL" for d in details)
