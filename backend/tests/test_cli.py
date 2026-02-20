"""Tests for CLI commands. Use mocked HTTP to avoid requiring a running backend."""

from __future__ import annotations

from unittest.mock import patch

from backend.cli import client, commands


def test_health_cmd_success() -> None:
    """Health command prints status when backend responds."""
    with patch.object(client, "get") as mock_get:
        mock_get.return_value.json.return_value = {"status": "ok", "env": "local"}
        commands.health_cmd(base_url="http://localhost:8000")
        mock_get.assert_called_once_with("/health", base_url="http://localhost:8000")


def test_analysis_cmd_json_output() -> None:
    """Analysis with JSON output prints raw JSON."""
    with patch.object(client, "get") as mock_get:
        mock_get.return_value.json.return_value = [
            {"symbol": "GME", "sentiment_score": 0.5, "mention_count": 10, "price_trend": "up", "composite_score": 0.7},
        ]
        with patch("backend.cli.output.print_json") as mock_json:
            commands.analysis_cmd(base_url="http://localhost:8000", output_fmt="json")
            mock_json.assert_called_once()


def test_portfolio_cmd_table_output() -> None:
    """Portfolio with table output prints formatted data."""
    with patch.object(client, "get") as mock_get:
        mock_get.return_value.json.return_value = {
            "total_positions": 2,
            "open_positions": 1,
            "closed_positions": 1,
            "realized_pl": 10.0,
            "unrealized_pl": 5.0,
            "win_rate": 1.0,
            "average_win": 10.0,
            "average_loss": None,
        }
        with patch("builtins.print") as mock_print:
            commands.portfolio_cmd(base_url="http://localhost:8000", output_fmt="table")
            assert mock_print.call_count >= 5


def test_stocks_list_cmd_empty() -> None:
    """Stocks list with no data prints message."""
    with patch.object(client, "get") as mock_get:
        mock_get.return_value.json.return_value = []
        with patch("backend.cli.output.print_table") as mock_table:
            commands.stocks_list_cmd(base_url="http://localhost:8000", output_fmt="table")
            mock_table.assert_not_called()
