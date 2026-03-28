# Data model: 012 Rolling robustness

## Entity: `LeaderFollowerRobustnessRun`

| Field | Type | Notes |
|-------|------|--------|
| `id` | int PK | autoincrement |
| `created_at` | datetime UTC | default now |
| `overall_start` | date | |
| `overall_end` | date | |
| `train_window_spec` | Text JSON | e.g. `{"unit":"months","value":6}` |
| `validate_window_spec` | Text JSON | |
| `test_window_spec` | Text JSON nullable | omit = two-window |
| `step_spec` | Text JSON | e.g. `{"unit":"months","value":1}` |
| `split_count` | int | number of splits generated |
| `grid_config_json` | Text | Full snapshot: sources, caps, ranking |
| `ranking_method` | str | e.g. `rolling_robustness_v1` |

**Relationships**: one-to-many `split_results`, `aggregates` (cascade delete).

## Entity: `LeaderFollowerRobustnessSplitResult`

| Field | Type | Notes |
|-------|------|--------|
| `id` | int PK | |
| `run_id` | FK → run | index |
| `config_hash` | str nullable | SHA-256 of canonical params |
| `params_json` | Text | merged `PaperTradingConfig` + grid point |
| `split_index` | int | 0-based |
| `train_start` … `test_end` | dates | test nullable |
| `train_metrics_json` | Text | `PaperSimulationMetrics` shape |
| `validate_metrics_json` | Text | |
| `test_metrics_json` | Text nullable | |

**Indexes**: `(run_id, split_index)`, `(run_id, config_hash)`.

## Entity: `LeaderFollowerRobustnessAggregate`

| Field | Type | Notes |
|-------|------|--------|
| `id` | int PK | |
| `run_id` | FK | |
| `config_hash` | str nullable | |
| `params_json` | Text | |
| `aggregate_metrics_json` | Text | medians, frac positive, ineligible, etc. |
| `robustness_score` | float | |
| `rank` | int | 1 = best |

## `aggregate_metrics_json` (illustrative keys)

- `splits_evaluated`, `positive_validation_splits`, `positive_test_splits`, `frac_positive_validation`, `frac_positive_test`
- `median_validation_cumulative_return_pct`, `median_test_cumulative_return_pct`
- `median_validation_max_drawdown_pct`, `median_train_to_validation_gap`
- `worst_validation_cumulative_return_pct`, `ineligible_splits`
- `validation_positive_sign_by_split` optional list for drill-down

## Validation rules

- `overall_start <= overall_end`
- Window specs: `unit` must be `months` in v1; positive integer `value`
- Step: `months` ≥ 1
- Non-overlapping windows per split enforced by generator + `validate_walk_forward_windows`
