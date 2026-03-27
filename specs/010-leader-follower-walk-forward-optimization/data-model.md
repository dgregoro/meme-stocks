# Data Model: Leader-Follower Walk-Forward Optimization

## Entity: `LeaderFollowerOptimizationRun`

| Field | Type | Notes |
|-------|------|--------|
| `id` | int PK | autoincrement |
| `created_at` | datetime TZ | UTC |
| `config_json` | text | Grid spec, `base_config`, ranking id + weights, optional `git_sha`/notes |
| `train_start` | date | |
| `train_end` | date | |
| `validate_start` | date | |
| `validate_end` | date | |
| `test_start` | date nullable | |
| `test_end` | date nullable | |
| `ranking_method` | string | e.g. `walk_forward_v1` |

**Relationships**: one-to-many `results`.

**Validation (application layer)**:

- `train_start <= train_end`, same for validate and test if present.
- `train_end < validate_start`, `validate_end < test_start` if test present.
- No overlapping intervals across train/validate/test.

---

## Entity: `LeaderFollowerOptimizationResult`

| Field | Type | Notes |
|-------|------|--------|
| `id` | int PK | |
| `run_id` | int FK | `leader_follower_optimization_runs.id`, CASCADE delete |
| `params_json` | text | One grid point (`PaperTradingConfig`-compatible subset + merged base) |
| `train_metrics_json` | text | `total_trades`, `skipped_count`, `cumulative_return_pct`, `avg_return_pct`, `win_rate`, `max_drawdown_pct` |
| `validate_metrics_json` | text | same shape |
| `test_metrics_json` | text nullable | same shape |
| `robustness_score` | float | |
| `rank` | int | 1 = best |

**Indexes**: `ix_optimization_results_run_id`, `ix_optimization_results_run_rank` (composite).

---

## Metrics JSON shape (per period)

```json
{
  "total_trades": 0,
  "skipped_count": 0,
  "cumulative_return_pct": 0.0,
  "avg_return_pct": 0.0,
  "win_rate": 0.0,
  "max_drawdown_pct": 0.0
}
```
