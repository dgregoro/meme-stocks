"""Tests for Alpaca client paging and safe end time."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import requests

from backend.app.clients.alpaca_data_client import (
    AlpacaDataClient,
    _feed_for_bars,
    compute_safe_end_time,
)


@pytest.mark.unit
def test_fetch_bars_page_returns_bars_and_next_token() -> None:
    """fetch_bars_page returns bars dict and next_page_token from response."""
    client = AlpacaDataClient(
        free_plan_mode=True,
        end_time_safety_minutes=20,
        feed="delayed_sip",
        api_key_id="key",
        api_secret_key="secret",
    )
    start = datetime(2026, 3, 1, 9, 30, 0, tzinfo=timezone.utc)
    end = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)

    with patch.object(requests, "get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "bars": {
                "AAPL": [
                    {
                        "t": "2026-03-01T09:30:00Z",
                        "o": 100.0,
                        "h": 101.0,
                        "l": 99.0,
                        "c": 100.5,
                        "v": 1000,
                        "n": 50,
                        "vw": 100.2,
                    }
                ]
            },
            "next_page_token": None,
        }
        bars, token = client.fetch_bars_page(
            symbols=["AAPL"],
            start=start,
            end=end,
            timeframe="1Min",
            feed="delayed_sip",
            page_token=None,
        )
        assert "AAPL" in bars
        assert len(bars["AAPL"]) == 1
        assert bars["AAPL"][0]["c"] == 100.5
        assert token is None
        call_args = mock_get.call_args
        assert call_args[1]["params"]["symbols"] == "AAPL"
        # delayed_sip is normalized to iex for historical bars (Alpaca 400 invalid feed)
        assert call_args[1]["params"]["feed"] == "iex"
        assert call_args[1]["params"]["limit"] == 10000


@pytest.mark.unit
def test_fetch_bars_page_paging_continues_until_no_token() -> None:
    """When next_page_token is present, request includes it; when None, paging stops."""
    client = AlpacaDataClient(
        free_plan_mode=True,
        end_time_safety_minutes=20,
        feed="delayed_sip",
        api_key_id="k",
        api_secret_key="s",
    )
    start = datetime(2026, 3, 1, 9, 30, 0, tzinfo=timezone.utc)
    end = datetime(2026, 3, 1, 11, 30, 0, tzinfo=timezone.utc)

    with patch.object(requests, "get") as mock_get:
        # First call: return token
        r1 = type(
            "R", (), {"status_code": 200, "json": lambda self=None: {"bars": {"AAPL": []}, "next_page_token": "token1"}}
        )()
        # Second call: no token
        r2 = type(
            "R", (), {"status_code": 200, "json": lambda self=None: {"bars": {"AAPL": []}, "next_page_token": None}}
        )()
        mock_get.side_effect = [r1, r2]

        bars1, token1 = client.fetch_bars_page(
            symbols=["AAPL"],
            start=start,
            end=end,
            page_token=None,
        )
        assert token1 == "token1"

        bars2, token2 = client.fetch_bars_page(
            symbols=["AAPL"],
            start=start,
            end=end,
            page_token="token1",
        )
        assert token2 is None
        assert mock_get.call_count == 2
        # Second call should have page_token
        assert mock_get.call_args_list[1][1]["params"].get("page_token") == "token1"


@pytest.mark.unit
def test_fetch_bars_page_429_triggers_retry_then_raises() -> None:
    """On 429, client retries with backoff; after max retries raises."""
    client = AlpacaDataClient(
        free_plan_mode=True,
        end_time_safety_minutes=20,
        feed="delayed_sip",
        api_key_id="k",
        api_secret_key="s",
    )
    start = datetime(2026, 3, 1, 9, 30, 0, tzinfo=timezone.utc)
    end = datetime(2026, 3, 1, 11, 30, 0, tzinfo=timezone.utc)

    with patch.object(requests, "get") as mock_get:
        mock_get.return_value.status_code = 429
        mock_get.return_value.text = "rate limited"
        with patch("backend.app.clients.alpaca_data_client.time.sleep") as mock_sleep:
            from backend.app.utils.errors import ExternalAPIError

            with pytest.raises(ExternalAPIError) as exc_info:
                client.fetch_bars_page(
                    symbols=["AAPL"],
                    start=start,
                    end=end,
                    page_token=None,
                )
            assert "429" in str(exc_info.value) or "rate" in str(exc_info.value).lower()
            assert mock_get.call_count >= 1
            assert mock_sleep.call_count >= 1


@pytest.mark.unit
def test_safe_end_time_used_when_free_plan_mode() -> None:
    """When free_plan_mode is True, request end param is clamped to safe end."""
    client = AlpacaDataClient(
        free_plan_mode=True,
        end_time_safety_minutes=20,
        feed="delayed_sip",
        api_key_id="k",
        api_secret_key="s",
    )
    now_utc = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    safe_end = compute_safe_end_time(now_utc, 20, True)
    end_caller = datetime(2026, 3, 1, 12, 30, 0, tzinfo=timezone.utc)

    with patch("backend.app.clients.alpaca_data_client.datetime") as mock_dt:
        mock_dt.now.return_value = now_utc
        with patch.object(requests, "get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"bars": {}, "next_page_token": None}
            client.fetch_bars_page(
                symbols=["AAPL"],
                start=datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc),
                end=end_caller,
                page_token=None,
            )
            params = mock_get.call_args[1]["params"]
            assert params["end"] == safe_end.isoformat().replace("+00:00", "Z")


@pytest.mark.unit
def test_feed_for_bars_normalizes_delayed_sip_to_iex() -> None:
    """delayed_sip is invalid for historical bars; normalize to iex."""
    assert _feed_for_bars("delayed_sip") == "iex"
    assert _feed_for_bars("iex") == "iex"
    assert _feed_for_bars("sip") == "sip"


@pytest.mark.unit
def test_fetch_bars_page_400_invalid_feed_retries_with_iex() -> None:
    """On 400 invalid feed, client retries once with feed=iex."""
    client = AlpacaDataClient(
        free_plan_mode=True,
        end_time_safety_minutes=20,
        feed="sip",  # non-iex feed that might be invalid
        api_key_id="k",
        api_secret_key="s",
    )
    start = datetime(2026, 3, 1, 9, 30, 0, tzinfo=timezone.utc)
    end = datetime(2026, 3, 1, 11, 30, 0, tzinfo=timezone.utc)
    captured_params: list[dict] = []
    r1 = type("R", (), {"status_code": 400, "text": '{"message":"invalid feed: sip"}'})()
    r2 = type(
        "R",
        (),
        {"status_code": 200, "json": lambda self=None: {"bars": {}, "next_page_token": None}},
    )()
    responses = [r1, r2]

    def capture_and_respond(*args: object, **kwargs: object) -> object:
        params = kwargs.get("params")
        if isinstance(params, dict):
            captured_params.append(dict(params))
        return responses.pop(0)

    with patch.object(requests, "get", side_effect=capture_and_respond):
        bars, token = client.fetch_bars_page(
            symbols=["AAPL"],
            start=start,
            end=end,
            feed="sip",
            page_token=None,
        )
    assert bars == {}
    assert token is None
    assert len(captured_params) == 2
    assert captured_params[0]["feed"] == "sip"
    assert captured_params[1]["feed"] == "iex"
