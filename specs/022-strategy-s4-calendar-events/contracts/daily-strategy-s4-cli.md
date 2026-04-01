# Contract: Daily strategy S4 CLI outputs

## Commands

| Command | Output |
|---------|--------|
| `evaluate daily-strategy s4` | Single JSON object: eval summary |
| `evaluate daily-strategy s4-merit` | Single JSON: `kind` `s4_merit_report` or `s4_merit_report_rolling` when `--splits` > 1 |
| `evaluate daily-strategy eval-bundle --strategy s4` | JSON: `kind` `strategy_merit_bundle`, `strategy` `s4` |

## Single-symbol eval (`run_s4_evaluation`)

- **strategy**: `"S4_calendar_events"`
- **symbol**: string
- **date_range**: `{ "start", "end" }` nullable strings
- **params**: `s4_include_*` booleans
- **horizons**: list of ints
- **counts**: map bucket key → event count
- **by_bucket**: bucket → horizon string → metrics (`metrics_from_returns`)
- On failure: **error** `"insufficient_price_data"` and **hint** (or config message); may include **by_bucket**: `{}`

## Pooled merit (`run_s4_merit_report`)

- **kind**: `"s4_merit_report"`
- **eval_window**: `{ start, end }`
- **symbols_requested**, **symbols_with_data**, **symbols_skipped**
- **params**: include flags + merit thresholds
- **horizons**: list
- **pooled_counts**: per bucket
- **baseline_metrics**, **by_bucket**, **vs_baseline_avg_pct**
- **checklist**: `{ pass, failures, note }`

## Rolling merit (`run_s4_merit_rolling_report`)

- **kind**: `"s4_merit_report_rolling"`
- **splits**: list of `{ eval_window, report }`
- **rollup**: excess sign stability (same shape as S2 rollup)

## Bundle (`run_strategy_merit_bundle`)

- **kind**: `"strategy_merit_bundle"`
- **strategy**: `"s4"`
- **single_window**: inner merit report
- **rolling**: optional rolling payload
- **summary**: automated gate summary

Persistence expects **eval_window** or **parent_window** with start/end for `build_merit_run_row`.
