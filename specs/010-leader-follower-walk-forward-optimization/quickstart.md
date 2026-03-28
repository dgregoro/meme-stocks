# Quickstart: Walk-Forward Optimization

## Prerequisites

- SQLite DB with **leader-follower signals** and **price_data** covering train, validate, and optional test windows.
- Same environment as `simulate leader-follower` (see feature `011`).

## 1. Define a small grid (JSON)

Example `grid.json`:

```json
{
  "base_config": {
    "entry_mode": "next_open",
    "exit_mode": "fixed_days",
    "per_trade_cost_pct": 0.1
  },
  "grid": {
    "holding_days": [1, 3, 5],
    "max_positions_per_event": [1, 2],
    "min_pair_score": [null, 0.5]
  },
  "ranking": {
    "method": "walk_forward_v1",
    "min_trades_validate": 5,
    "w_deg": 0.5,
    "w_dd": 0.25
  }
}
```

## 2. Run CLI

From repo root:

```bash
export SPECIFY_FEATURE=010-leader-follower-walk-forward-optimization  # if multiple 010-* specs exist
python -m backend.app.cli optimize leader-follower \
  --train-start 2025-02-01 --train-end 2025-10-31 \
  --validate-start 2025-11-01 --validate-end 2026-01-31 \
  --grid-file ./path/to/grid.json
```

Optional test window:

```bash
  --test-start 2026-02-01 --test-end 2026-03-20
```

## 3. Inspect via API

```bash
curl -s "http://localhost:8000/api/leader-follower/optimization/runs?limit=10"
curl -s "http://localhost:8000/api/leader-follower/optimization/1/top-results?limit=5"
```

## 4. Interpretation

- Prefer configs with high **robustness_score** and adequate **validate** `total_trades`.
- Do **not** pick configs solely on train cumulative return.
- If all scores are strongly negative or trade counts are tiny, widen data or simplify grid before drawing conclusions.
