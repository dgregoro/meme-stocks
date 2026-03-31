"""Unit tests for `backend.app.scripts.run_causal` CLI (mocked HTTP)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.app.scripts import run_causal as run_causal_mod


@pytest.mark.unit
def test_parse_args_reads_symbol_and_days() -> None:
    with patch.object(sys, "argv", ["run_causal", "--symbol", "GME", "--days", "42"]):
        ns = run_causal_mod.parse_args()
    assert ns.symbol == "GME"
    assert ns.days == 42


@pytest.mark.unit
def test_main_success_prints_summary(tmp_path: Path) -> None:
    payload = {
        "symbol": "GME",
        "sample_size": 50,
        "freq": "1h",
        "mention_xcorr": [{"lag": 0, "corr": 0.1, "n": 40}],
        "sentiment_xcorr": [{"lag": 1, "corr": -0.05, "n": 38}],
        "predictive": [{"metric": "r2", "value": 0.02}],
        "placebo": [{"metric": "r2", "value": 0.0}],
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status = MagicMock()
    out_file = tmp_path / "out.json"
    fake_args = MagicMock(
        symbol="GME",
        days=60,
        freq="1h",
        max_lag=12,
        host="http://127.0.0.1:8000",
        output=str(out_file),
    )
    with (
        patch.object(run_causal_mod, "parse_args", return_value=fake_args),
        patch.object(run_causal_mod.requests, "get", return_value=mock_resp),
    ):
        run_causal_mod.main()
    assert out_file.exists()
    saved = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved["symbol"] == "GME"


@pytest.mark.unit
def test_main_insufficient_data_saves_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    payload = {
        "symbol": "X",
        "freq": "1h",
        "reason": "too_few_bars",
        "buckets_available": 3,
        "min_required": 10,
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status = MagicMock()
    out_file = tmp_path / "ins.json"
    fake_args = MagicMock(
        symbol="X",
        days=10,
        freq="1h",
        max_lag=5,
        host="http://localhost:8000",
        output=str(out_file),
    )
    with (
        patch.object(run_causal_mod, "parse_args", return_value=fake_args),
        patch.object(run_causal_mod, "sys") as mock_sys,
        patch.object(run_causal_mod.requests, "get", return_value=mock_resp),
    ):
        mock_sys.exit.side_effect = SystemExit(1)
        with pytest.raises(SystemExit):
            run_causal_mod.main()
    captured = capsys.readouterr()
    assert "INSUFFICIENT DATA" in captured.out
    assert out_file.exists()


@pytest.mark.unit
def test_main_http_404_exits(capsys: pytest.CaptureFixture[str]) -> None:
    err = run_causal_mod.requests.HTTPError()
    err.response = MagicMock(status_code=404)
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = err
    fake_args = MagicMock(
        symbol="ZZZ",
        days=10,
        freq="1h",
        max_lag=5,
        host="http://localhost:8000",
        output=None,
    )
    with (
        patch.object(run_causal_mod, "parse_args", return_value=fake_args),
        patch.object(run_causal_mod, "sys") as mock_sys,
        patch.object(run_causal_mod.requests, "get", return_value=mock_resp),
    ):
        mock_sys.exit.side_effect = SystemExit(1)
        with pytest.raises(SystemExit):
            run_causal_mod.main()
    assert "404" in capsys.readouterr().out


@pytest.mark.unit
def test_main_request_exception_exits(capsys: pytest.CaptureFixture[str]) -> None:
    fake_args = MagicMock(
        symbol="Y",
        days=10,
        freq="1h",
        max_lag=5,
        host="http://localhost:8000",
        output=None,
    )
    with (
        patch.object(run_causal_mod, "parse_args", return_value=fake_args),
        patch.object(run_causal_mod, "sys") as mock_sys,
        patch.object(
            run_causal_mod.requests,
            "get",
            side_effect=run_causal_mod.requests.Timeout("timed out"),
        ),
    ):
        mock_sys.exit.side_effect = SystemExit(1)
        with pytest.raises(SystemExit):
            run_causal_mod.main()
    assert "ERROR" in capsys.readouterr().out


@pytest.mark.unit
def test_main_zero_sample_exits() -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"symbol": "Z", "sample_size": 0, "freq": "1h"}
    mock_resp.raise_for_status = MagicMock()
    fake_args = MagicMock(
        symbol="Z",
        days=10,
        freq="1h",
        max_lag=5,
        host="http://localhost:8000",
        output=None,
    )
    with (
        patch.object(run_causal_mod, "parse_args", return_value=fake_args),
        patch.object(run_causal_mod, "sys") as mock_sys,
        patch.object(run_causal_mod.requests, "get", return_value=mock_resp),
    ):
        mock_sys.exit.side_effect = SystemExit(1)
        with pytest.raises(SystemExit):
            run_causal_mod.main()
