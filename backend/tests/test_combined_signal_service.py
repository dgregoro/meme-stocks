"""Tests for combined_signal_service."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from backend.app.services.combined_signal_service import (
    CombinedEvaluation,
    SignalEvaluated,
    evaluate,
    from_activity_signal,
    from_rsi_signal,
    parse_signal_metadata,
    serialize_signal_metadata,
)
from backend.app.services.activity_detector import ActivitySignal


@pytest.mark.unit
def test_one_signal_threshold_met_false() -> None:
    """One signal only => threshold_met False (SC-001)."""
    signals = [
        SignalEvaluated("volume_spike", "Volume 2.5x average", True, 2.0, None),
    ]
    with patch("backend.app.services.combined_signal_service.get_settings") as mock:
        mock.return_value.combined_signal_threshold = 2.0
        ev = evaluate("GME", signals)
    assert ev.threshold_met is False  # Only 1 fired


@pytest.mark.unit
def test_two_signals_below_threshold() -> None:
    """Two signals, score below threshold => threshold_met False."""
    signals = [
        SignalEvaluated("volume_spike", "Volume 2x average", True, 1.0, None),
        SignalEvaluated("sentiment_shift", "Shift +0.3", True, 1.0, None),
    ]
    with patch("backend.app.services.combined_signal_service.get_settings") as mock:
        mock.return_value.combined_signal_threshold = 4.0
        ev = evaluate("GME", signals)
    assert ev.combined_score == 2.0
    assert ev.threshold_met is False


@pytest.mark.unit
def test_two_signals_above_threshold() -> None:
    """Two+ signals, score >= threshold => threshold_met True."""
    signals = [
        SignalEvaluated("volume_spike", "Volume 2.5x average", True, 1.0, None),
        SignalEvaluated("price_movement", "Price +6%", True, 2.0, None),
        SignalEvaluated("sentiment_shift", "Shift +0.4", True, 2.0, None),
    ]
    with patch("backend.app.services.combined_signal_service.get_settings") as mock:
        mock.return_value.combined_signal_threshold = 4.0
        ev = evaluate("GME", signals)
    assert ev.combined_score == 5.0
    assert ev.threshold_met is True


@pytest.mark.unit
def test_missing_input_no_crash() -> None:
    """Missing signal input => score from available only, no crash."""
    signals = [
        SignalEvaluated("volume_spike", None, False, 0.0, "No signal"),
        SignalEvaluated("sentiment_shift", "Shift +0.5", True, 2.0, None),
    ]
    with patch("backend.app.services.combined_signal_service.get_settings") as mock:
        mock.return_value.combined_signal_threshold = 4.0
        ev = evaluate("GME", signals)
    assert ev.combined_score == 2.0
    assert ev.threshold_met is False


@pytest.mark.unit
def test_serialize_parse_round_trip() -> None:
    """Serialize and parse round-trip preserves data."""
    ts = datetime.now(timezone.utc)
    ev = CombinedEvaluation(
        symbol="GME",
        signals_evaluated=(
            SignalEvaluated("volume_spike", "2.5x avg", True, 1.0, None),
            SignalEvaluated("rsi_signal", None, False, 0.0, "neutral"),
        ),
        combined_score=1.0,
        threshold=4.0,
        threshold_met=False,
        evaluation_timestamp=ts,
    )
    s = serialize_signal_metadata(ev)
    parsed = parse_signal_metadata(s)
    assert parsed is not None
    assert parsed["combined_score"] == 1.0
    assert parsed["threshold"] == 4.0
    assert len(parsed["signals_evaluated"]) == 2
    assert parsed["signals_evaluated"][0]["signal_type"] == "volume_spike"
    assert parsed["signals_evaluated"][0]["fired"] is True
    assert parsed["signals_evaluated"][1]["fired"] is False


@pytest.mark.unit
def test_parse_invalid_json_returns_none() -> None:
    """Parse invalid JSON => None."""
    assert parse_signal_metadata("not json") is None
    assert parse_signal_metadata("") is None
    assert parse_signal_metadata(None) is None


@pytest.mark.unit
def test_from_activity_signal_fired() -> None:
    """Adapter converts ActivitySignal to SignalEvaluated when fired."""
    sig = ActivitySignal(kind="volume_spike", severity="high", message="2.5x avg")
    out = from_activity_signal(sig, "volume_spike", 1.0)
    assert out.signal_type == "volume_spike"
    assert out.fired is True
    assert out.contribution == 1.0


@pytest.mark.unit
def test_from_activity_signal_none() -> None:
    """Adapter returns fired=False when signal is None."""
    out = from_activity_signal(None, "volume_spike", 1.0)
    assert out.signal_type == "volume_spike"
    assert out.fired is False
    assert out.contribution == 0.0


@pytest.mark.unit
def test_from_rsi_signal_overbought() -> None:
    """RSI overbought/oversold => fired."""
    out = from_rsi_signal("overbought", 75.0, 1.0)
    assert out.fired is True
    assert out.contribution == 1.0


@pytest.mark.unit
def test_from_rsi_signal_neutral() -> None:
    """RSI neutral => fired=False."""
    out = from_rsi_signal("neutral", 50.0, 1.0)
    assert out.fired is False
    assert out.contribution == 0.0
