"""Hints when daily-strategy evaluation lacks price_data."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.app.services.daily_frequency_strategy_research import _price_data_hint


@pytest.mark.unit
def test_price_data_hint_missing_stock() -> None:
    db = MagicMock()
    with patch("backend.app.services.daily_frequency_strategy_research.StockRepository") as repo_cls:
        repo_cls.return_value.get.return_value = None
        h = _price_data_hint(db, "SPY", 0, 0)
        assert "seed stocks" in h
        assert "SPY" in h


@pytest.mark.unit
def test_price_data_hint_empty_price_table() -> None:
    db = MagicMock()
    stock = MagicMock()
    with patch("backend.app.services.daily_frequency_strategy_research.StockRepository") as repo_cls:
        repo_cls.return_value.get.return_value = stock
        h = _price_data_hint(db, "SPY", 0, 0)
        assert "backfill daily-prices" in h
        assert "ALPACA" in h


@pytest.mark.unit
def test_price_data_hint_need_more_bars() -> None:
    db = MagicMock()
    stock = MagicMock()
    with patch("backend.app.services.daily_frequency_strategy_research.StockRepository") as repo_cls:
        repo_cls.return_value.get.return_value = stock
        h = _price_data_hint(db, "SPY", 50, 50)
        assert "more trading days" in h


@pytest.mark.unit
def test_price_data_hint_rows_fail_validation() -> None:
    db = MagicMock()
    stock = MagicMock()
    with patch("backend.app.services.daily_frequency_strategy_research.StockRepository") as repo_cls:
        repo_cls.return_value.get.return_value = stock
        h = _price_data_hint(db, "SPY", 5, 0)
        assert "none passed validation" in h
