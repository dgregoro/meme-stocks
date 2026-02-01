"""Tests for logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from backend.app.config import get_settings
from backend.app.utils.logging_config import configure_logging


def test_configure_logging_creates_log_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """configure_logging creates the log directory and file."""
    import tempfile

    tmp = Path(tempfile.mkdtemp())
    log_file = tmp / "test_app.log"
    monkeypatch.setenv("LOG_FILE", str(log_file))
    get_settings.cache_clear()

    try:
        configure_logging()
        assert log_file.exists()
        # yfinance logger should have file handler only (no console)
        yf_logger = logging.getLogger("yfinance")
        assert len(yf_logger.handlers) == 1
        assert isinstance(yf_logger.handlers[0], logging.FileHandler)
    finally:
        get_settings.cache_clear()
