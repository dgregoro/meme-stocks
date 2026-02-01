"""Configure logging so third-party noise (yfinance, pandas, etc.) goes to file only."""

from __future__ import annotations

import logging
from pathlib import Path

from backend.app.config import get_settings


def configure_logging() -> None:
    """Set up logging: noisy third-party loggers write to file only, not the terminal.

    yfinance emits messages like "possibly delisted; no timezone found" for some symbols.
    These are redirected to the log file so the terminal stays clean.
    """
    settings = get_settings()
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    file_handler.setFormatter(file_formatter)

    # Loggers that emit noisy messages (e.g. "possibly delisted; no timezone found")
    # we want in file only, not on terminal
    noisy_logger_names = ("yfinance", "pandas", "urllib3")
    for name in noisy_logger_names:
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
