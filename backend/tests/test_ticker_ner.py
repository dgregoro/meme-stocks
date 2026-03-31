"""Tests for optional ticker NER helper."""

from __future__ import annotations

import pytest

from backend.app.utils.ticker_ner import extract_ner_candidates


@pytest.mark.unit
def test_extract_ner_candidates_without_transformers() -> None:
    """When transformers is unavailable, return empty set (no crash)."""
    out = extract_ner_candidates("Buy AAPL and MSFT")
    assert out == set()
