"""Tests for walk-forward optimization service."""

from __future__ import annotations

from datetime import date

import pytest

from backend.app.services.leader_follower_paper_trading_service import PaperSimulationMetrics
from backend.app.services.leader_follower_walk_forward_service import (
    WalkForwardValidationError,
    expand_grid_points,
    load_grid_config_from_dict,
    robustness_walk_forward_v1,
    validate_walk_forward_windows,
)


@pytest.mark.unit
def test_validate_walk_forward_windows_ok() -> None:
    validate_walk_forward_windows(
        date(2025, 1, 1),
        date(2025, 6, 30),
        date(2025, 7, 1),
        date(2025, 9, 30),
        date(2025, 10, 1),
        date(2025, 12, 31),
    )


@pytest.mark.unit
def test_validate_rejects_train_validate_overlap() -> None:
    with pytest.raises(WalkForwardValidationError, match="train period must end"):
        validate_walk_forward_windows(
            date(2025, 1, 1),
            date(2025, 8, 1),
            date(2025, 7, 1),
            date(2025, 9, 30),
            None,
            None,
        )


@pytest.mark.unit
def test_expand_grid_rejects_too_many() -> None:
    cfg = load_grid_config_from_dict(
        {
            "grid": {
                "holding_days": list(range(20)),
                "max_positions_per_event": list(range(20)),
            },
            "ranking": {"method": "walk_forward_v1"},
        }
    )
    with pytest.raises(WalkForwardValidationError, match="Grid has"):
        expand_grid_points(cfg, max_combinations=50)


@pytest.mark.unit
def test_robustness_penalizes_low_validate_trades() -> None:
    tr = PaperSimulationMetrics(10, 0, 0.5, 1.0, 5.0, 2.0)
    va = PaperSimulationMetrics(2, 0, 0.5, 1.0, 10.0, 1.0)
    s = robustness_walk_forward_v1(
        tr, va, min_trades_validate=5, w_deg=0.5, w_dd=0.25
    )
    assert s < -9000


@pytest.mark.unit
def test_robustness_validation_first() -> None:
    tr = PaperSimulationMetrics(10, 0, 0.5, 1.0, 20.0, 1.0)
    va_good = PaperSimulationMetrics(10, 0, 0.5, 1.0, 10.0, 2.0)
    va_bad = PaperSimulationMetrics(10, 0, 0.5, 1.0, 5.0, 2.0)
    s_good = robustness_walk_forward_v1(
        tr, va_good, min_trades_validate=5, w_deg=0.5, w_dd=0.25
    )
    s_bad = robustness_walk_forward_v1(
        tr, va_bad, min_trades_validate=5, w_deg=0.5, w_dd=0.25
    )
    assert s_good > s_bad


@pytest.mark.unit
def test_load_grid_unknown_key() -> None:
    with pytest.raises(WalkForwardValidationError, match="Unsupported grid keys"):
        load_grid_config_from_dict(
            {
                "grid": {"holding_days": [1], "fake_param": [1]},
                "ranking": {"method": "walk_forward_v1"},
            }
        )
