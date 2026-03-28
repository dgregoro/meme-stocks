# Quickstart: Rolling walk-forward robustness (012)

## Prerequisites

- DB with `leader_follower_signals` and `price_data` covering `[overall_start, overall_end]`.
- Same assumptions as walk-forward optimization (`010`): evaluation uses **existing** signals.

## Caps

- Grid Cartesian product and explicit candidate list length: each limited by **`leader_follower_optimization_max_grid_points`** (default 256).
- **`leader_follower_robustness_max_evaluations`**: `splits × candidates` must not exceed this value (default 5000). CLI fails with a clear error if exceeded.

## Grid file (Mode A)

Same shape as `010`, but **`ranking.method` must be `rolling_robustness_v1`**.

```json
{
  "base_config": {
    "entry_mode": "next_open",
    "exit_mode": "fixed_days",
    "per_trade_cost_pct": 0.1
  },
  "grid": {
    "holding_days": [1, 3, 5],
    "max_positions_per_event": [1, 2]
  },
  "ranking": {
    "method": "rolling_robustness_v1",
    "min_trades_validate": 5,
    "w_dd": 0.25,
    "w_gap": 0.5,
    "w_frac": 10.0,
    "penalty_ineligible": 25.0
  }
}
```

## Candidates file (Mode B)

```json
{
  "base_config": { "per_trade_cost_pct": 0.1 },
  "candidates": [
    { "holding_days": 3, "max_positions_per_event": 2 },
    { "holding_days": 5, "max_positions_per_event": 1 }
  ],
  "ranking": {
    "method": "rolling_robustness_v1",
    "min_trades_validate": 5
  }
}
```

## CLI

```bash
python -m backend.app.cli robustness leader-follower \
  --overall-start 2024-01-01 \
  --overall-end 2025-12-31 \
  --train-window-months 6 \
  --validate-window-months 2 \
  --test-window-months 1 \
  --step-months 1 \
  --grid-file path/to/grid.json
```

Omit optional test:

```bash
python -m backend.app.cli robustness leader-follower \
  --overall-start 2024-01-01 \
  --overall-end 2025-06-30 \
  --train-window-months 6 \
  --validate-window-months 2 \
  --step-months 2 \
  --candidates-file path/to/candidates.json
```

## API

- `GET /api/leader-follower/robustness/runs?limit=50`
- `GET /api/leader-follower/robustness/{run_id}`
- `GET /api/leader-follower/robustness/{run_id}/top-results?limit=20`
- `GET /api/leader-follower/robustness/{run_id}/splits?limit=100&offset=0`
  Optional: `config_key=<sha256>`, `split_index=<n>`

## Calendar note

v1 uses **calendar months**. For cleanest boundaries, use **`overall_start`** on the **first day of a month**.
