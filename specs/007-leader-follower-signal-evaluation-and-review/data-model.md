# Data Model: Leader-Follower Signal Evaluation

**Feature**: 007-leader-follower-signal-evaluation-and-review
**Date**: 2026-03-18

## No New Persistent Entities

Evaluation is **computed on demand** from existing data. No new database tables or ORM models.

## Existing Entities Used

### LeaderFollowerSignal

| Field            | Type   | Purpose                                      |
|------------------|--------|----------------------------------------------|
| id               | int    | Signal identifier                            |
| leader_symbol    | str    | Leader ticker                                |
| follower_symbol  | str    | Follower ticker (target for forward return)  |
| group_id         | str    | Stock group                                   |
| signal_date      | date   | Event date; entry = follower close on this    |
| strength_score   | float  | Signal strength                              |
| leader_return_pct| float  | Leader return at event                        |
| leader_volume_ratio | float | Leader volume ratio                         |
| metrics_json     | str?   | Optional metrics                             |
| created_at       | datetime | Creation timestamp                          |

### PriceData

| Field        | Type   | Purpose                    |
|--------------|--------|----------------------------|
| stock_symbol | str    | Ticker                     |
| date         | date   | Trading date               |
| close        | float  | Closing price (entry/target)|

## In-Memory / Response Structures

### SignalEvaluation (service output)

Per-signal evaluation; not persisted.

| Field            | Type     | Purpose                                      |
|------------------|----------|----------------------------------------------|
| signal_id        | int      | From LeaderFollowerSignal.id                  |
| signal_date      | date     | Event date                                   |
| created_at       | str      | ISO timestamp                                |
| leader_symbol    | str      | Leader ticker                                |
| follower_symbol  | str      | Follower ticker                              |
| entry_price      | float?   | Follower close on signal_date; null if missing|
| horizons         | dict     | e.g. {"1d": {fwd_return_pct, win}, ...}      |

### PairAggregate (service output)

Per (leader, follower) pair; not persisted.

| Field           | Type   | Purpose                             |
|-----------------|--------|-------------------------------------|
| leader_symbol   | str    | Leader ticker                       |
| follower_symbol | str    | Follower ticker                     |
| signal_count    | int    | Number of signals                   |
| horizons        | dict   | Win rate, avg_return_pct per horizon |

### SummaryMetrics (service output)

| Field                | Type   | Purpose                              |
|----------------------|--------|--------------------------------------|
| total_signals        | int    | Total signal count                   |
| signals_per_day      | float  | total / days in range                |
| date_range           | dict   | since, until                         |
| by_horizon           | dict   | 1d/3d/5d: win_rate, avg_return_pct, etc. |
| duplicate_overlap   | dict   | repeat_pair_in_window, window_days   |

## Validation Rules

- `signal_date` must exist; no fabrication.
- Forward return: only when both entry close and target close exist.
- `evaluable_count` ≤ `total_signals` per horizon.
- `min_sample` for pair rankings: default 2; exposed in API.
