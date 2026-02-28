"""Tests for symbol universe functionality."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.data.database import Base
from backend.app.data.repositories.symbol_universe_repo import SymbolUniverseRepository
from backend.app.models.symbol_universe import SymbolUniverse
from backend.app.services.symbol_universe_service import SymbolUniverseService
from backend.app.utils.ticker_extractor import (
    clear_symbol_universe_cache,
    extract_tickers,
)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Create an in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_symbols(db_session: Session) -> list[SymbolUniverse]:
    """Create sample symbols in the universe."""
    symbols = [
        SymbolUniverse(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            is_etf=False,
            is_active=True,
            last_seen=datetime.now(timezone.utc),
        ),
        SymbolUniverse(
            symbol="MSFT",
            name="Microsoft Corporation",
            exchange="NASDAQ",
            is_etf=False,
            is_active=True,
            last_seen=datetime.now(timezone.utc),
        ),
        SymbolUniverse(
            symbol="GME",
            name="GameStop Corp.",
            exchange="NYSE",
            is_etf=False,
            is_active=True,
            last_seen=datetime.now(timezone.utc),
        ),
    ]
    for symbol in symbols:
        db_session.add(symbol)
    db_session.commit()
    return symbols


def test_symbol_universe_repository_add_and_get(db_session: Session) -> None:
    """Test adding and retrieving symbols from repository."""
    repo = SymbolUniverseRepository(db_session)

    symbol = SymbolUniverse(
        symbol="TEST",
        name="Test Company",
        exchange="NASDAQ",
        is_etf=False,
        is_active=True,
        last_seen=datetime.now(timezone.utc),
    )

    repo.add(symbol)
    db_session.commit()

    retrieved = repo.get("TEST")
    assert retrieved is not None
    assert retrieved.symbol == "TEST"
    assert retrieved.name == "Test Company"


def test_symbol_universe_repository_upsert(db_session: Session) -> None:
    """Test upsert functionality."""
    repo = SymbolUniverseRepository(db_session)

    # Insert new symbol
    symbol = SymbolUniverse(
        symbol="NEW",
        name="New Company",
        exchange="NASDAQ",
        is_etf=False,
        is_active=True,
    )
    repo.upsert(symbol)
    db_session.commit()

    assert repo.get("NEW") is not None

    # Update existing symbol
    symbol.name = "Updated Company"
    repo.upsert(symbol)
    db_session.commit()

    updated = repo.get("NEW")
    assert updated is not None
    assert updated.name == "Updated Company"


def test_symbol_universe_repository_get_symbols_set(db_session: Session, sample_symbols: list[SymbolUniverse]) -> None:
    """Test getting symbols as a set."""
    repo = SymbolUniverseRepository(db_session)
    symbols_set = repo.get_symbols_set(active_only=True)

    assert "AAPL" in symbols_set
    assert "MSFT" in symbols_set
    assert "GME" in symbols_set
    assert len(symbols_set) == 3


def test_symbol_universe_repository_count(db_session: Session, sample_symbols: list[SymbolUniverse]) -> None:
    """Test counting symbols."""
    repo = SymbolUniverseRepository(db_session)
    count = repo.count(active_only=True)

    assert count == 3


@patch("backend.app.services.symbol_universe_service.requests.get")
def test_symbol_universe_service_refresh_from_nasdaq(mock_get: MagicMock, db_session: Session) -> None:
    """Test refreshing symbol universe from SEC EDGAR."""
    # Mock SEC EDGAR response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corporation"},
        "2": {"cik_str": 1326380, "ticker": "GME", "title": "GameStop Corp."},
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    service = SymbolUniverseService(db_session)
    stats = service.refresh_from_nasdaq()

    assert stats["inserted"] == 3
    assert stats["total"] == 3

    # Verify symbols were added
    repo = SymbolUniverseRepository(db_session)
    assert repo.get("AAPL") is not None
    assert repo.get("MSFT") is not None
    assert repo.get("GME") is not None


def test_symbol_universe_service_get_symbols_set(db_session: Session, sample_symbols: list[SymbolUniverse]) -> None:
    """Test getting symbols set from service."""
    service = SymbolUniverseService(db_session)
    symbols_set = service.get_symbols_set(active_only=True)

    assert "AAPL" in symbols_set
    assert "MSFT" in symbols_set
    assert "GME" in symbols_set


def test_ticker_extractor_uses_symbol_universe(db_session: Session, sample_symbols: list[SymbolUniverse]) -> None:
    """Test that ticker extractor uses symbol universe when available."""
    clear_symbol_universe_cache()
    universe = {s.symbol for s in sample_symbols}  # AAPL, MSFT, GME

    with patch("backend.app.utils.ticker_extractor.load_symbol_universe_from_db", return_value=universe):
        text = "I love AAPL and MSFT but also MOON and BUY"
        tickers = extract_tickers(text, use_symbol_universe=True)

    assert "AAPL" in tickers
    assert "MSFT" in tickers
    assert "MOON" not in tickers
    assert "BUY" not in tickers


def test_ticker_extractor_fallback_without_universe() -> None:
    """Test that ticker extractor falls back to auto-discovery when universe is empty."""
    # Clear cache
    clear_symbol_universe_cache()

    # Mock empty universe
    with patch("backend.app.utils.ticker_extractor.load_symbol_universe_from_db", return_value=set()):
        text = "I love AAPL and MSFT"
        tickers = extract_tickers(text, use_symbol_universe=True)

        # Should still extract tickers in auto-discovery mode
        assert "AAPL" in tickers
        assert "MSFT" in tickers


def test_ticker_extractor_without_universe_flag() -> None:
    """Test that ticker extractor works without symbol universe."""
    text = "I love AAPL and MSFT but also MOON"

    # Extract without using symbol universe
    tickers = extract_tickers(text, use_symbol_universe=False)

    # Should extract all potential tickers; dangerous symbols (MOON) need strong evidence
    assert "AAPL" in tickers
    assert "MSFT" in tickers
    assert "MOON" not in tickers


# --- Context and dangerous-symbol policy tests (Step 6) ---


def test_cashtag_on_includes_on() -> None:
    """$ON => includes ON (hard evidence)."""
    tickers = extract_tickers("$ON is the ticker", use_symbol_universe=False)
    assert "ON" in tickers


def test_on_up_5_percent_includes_on() -> None:
    """ON is up 5% after earnings => includes ON (market context)."""
    tickers = extract_tickers(
        "ON is up 5% after earnings",
        known_symbols={"ON"},
    )
    assert "ON" in tickers


def test_on_the_table_excludes_on() -> None:
    """ON the table => excludes ON (no market context, dangerous)."""
    tickers = extract_tickers("ON the table", known_symbols={"ON"})
    assert "ON" not in tickers


def test_i_like_it_excludes_i_and_it() -> None:
    """I like it => excludes IT and I (dangerous, no hard evidence)."""
    tickers = extract_tickers("I like it", use_symbol_universe=False)
    assert "IT" not in tickers
    assert "I" not in tickers


def test_ai_model_training_excludes_ai() -> None:
    """AI model training => excludes AI (dangerous, no market context)."""
    tickers = extract_tickers("AI model training", known_symbols={"AI"})
    assert "AI" not in tickers


def test_ai_up_3_percent_includes_ai() -> None:
    """AI up 3% => includes AI (if in universe, market context)."""
    tickers = extract_tickers("AI up 3%", known_symbols={"AI"})
    assert "AI" in tickers


def test_ticker_list_includes_on_nvda_tsla() -> None:
    """ON, NVDA, TSLA ripping => includes ON, NVDA, TSLA (ticker list context)."""
    tickers = extract_tickers(
        "ON, NVDA, TSLA ripping today",
        known_symbols={"ON", "NVDA", "TSLA"},
    )
    assert "ON" in tickers
    assert "NVDA" in tickers
    assert "TSLA" in tickers


def test_auto_discovery_excludes_dangerous_without_hard_evidence() -> None:
    """When universe is empty (auto-discovery): exclude IT/ON/OR unless hard evidence."""
    clear_symbol_universe_cache()
    with patch("backend.app.utils.ticker_extractor.load_symbol_universe_from_db", return_value=set()):
        # No hard evidence => exclude dangerous word-tickers
        tickers = extract_tickers("IT and ON and OR are words", use_symbol_universe=True)
        assert "IT" not in tickers
        assert "ON" not in tickers
        assert "OR" not in tickers
        # Hard evidence => keep
        tickers2 = extract_tickers("$ON only", use_symbol_universe=True)
        assert "ON" in tickers2
