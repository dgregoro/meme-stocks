# Data Model: Leader-Follower Paper Trading (011)

## Tables

### `leader_follower_paper_runs`

| Column | Type | Notes |
|--------|------|--------|
| `id` | INTEGER PK | Autoincrement |
| `created_at` | DATETIME TZ | Run creation time |
| `config_json` | TEXT NOT NULL | JSON serialization of execution config |
| `start_date` | DATE NOT NULL | Simulation window (signals filtered) |
| `end_date` | DATE NOT NULL | Inclusive end |
| `total_trades` | INTEGER NOT NULL | Executed trades |
| `skipped_count` | INTEGER NOT NULL | Signals skipped (missing price, filters) |
| `win_rate` | REAL | Fraction of trades with net_return_pct > 0 |
| `avg_return_pct` | REAL | Mean net_return_pct |
| `cumulative_return_pct` | REAL | Compound: (equity_end - 1) * 100 |
| `max_drawdown_pct` | REAL | Max peak-to-trough on equity curve (positive number) |

### `leader_follower_paper_trades`

| Column | Type | Notes |
|--------|------|--------|
| `id` | INTEGER PK | Autoincrement |
| `run_id` | INTEGER FK → `leader_follower_paper_runs.id` | ON DELETE CASCADE |
| `leader_symbol` | VARCHAR(16) | |
| `follower_symbol` | VARCHAR(16) | |
| `signal_date` | DATE | From signal |
| `signal_id` | INTEGER NULL FK → `leader_follower_signals.id` | Optional traceability |
| `entry_price` | REAL NOT NULL | |
| `exit_price` | REAL NOT NULL | |
| `entry_time` | DATETIME TZ | E.g. UTC noon on entry date (documented convention) |
| `exit_time` | DATETIME TZ | E.g. UTC noon on exit date |
| `holding_period_days` | INTEGER NOT NULL | Trading days between entry and exit |
| `gross_return_pct` | REAL NOT NULL | |
| `net_return_pct` | REAL NOT NULL | After cost |

Indexes: `run_id`, `(leader_symbol, signal_date)`.

## Config JSON (config_json)

Example shape:

```json
{
  "entry_mode": "next_open",
  "exit_mode": "fixed_days",
  "holding_days": 3,
  "max_positions_per_event": 2,
  "min_pair_score": null,
  "per_trade_cost_pct": 0.1
}
```
