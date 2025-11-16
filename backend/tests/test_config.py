from __future__ import annotations

import pytest

from backend.app.config import Settings, get_settings


def test_get_settings_uses_defaults_when_env_not_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ensure related environment variables are cleared
    monkeypatch.delenv("API_HOST", raising=False)
    monkeypatch.delenv("API_PORT", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = get_settings()

    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000
    assert settings.log_level == "INFO"
    assert settings.database_url.startswith("sqlite:///")
    # Analysis thresholds should have sane defaults
    assert settings.sentiment_positive_threshold == 0.3
    assert settings.sentiment_negative_threshold == -0.2
    assert settings.volume_spike_threshold == 2.0
    assert settings.price_movement_threshold_pct == 5.0
    assert settings.sentiment_shift_threshold == 0.3


def test_settings_can_be_overridden_via_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    monkeypatch.setenv("API_PORT", "9000")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")

    # Clear cache to ensure fresh settings are loaded
    Settings.Config.case_sensitive = False  # no-op but ensures class referenced

    # Bypass cache for this test by constructing Settings directly
    settings = Settings()

    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 9000
    assert settings.log_level == "DEBUG"
    assert settings.database_url == "sqlite:///./test.db"
