# Contract: Daily strategy S6 CLI

## Commands

### `evaluate daily-strategy s6`

- **Required**: `--symbol` / `-s` (leg A), `--leg-b` (leg B ticker)
- **Optional**: `--start`, `--end`, `--preflight-only`, `--ensure-data`
- **Output**: JSON summary with `strategy: S6_slow_pairs`, `params.leg_b`, `by_regime`, `horizons`, `counts`

### `evaluate daily-strategy s6-merit`

- **Required**: `--start`, `--end`, one of `--symbols`, `--symbols-file`, `--all-stocks` (leg A list), **`--leg-b`**
- **Optional**: `--splits`, `--split-mode`, `--trading-calendar-symbols`, `--preflight-only`, `--ensure-data`, `--append-jsonl`, `--no-persist`
- **Output**: Same envelope as `s3_merit_report` / `s5_merit_report` (`kind`, `by_regime`, checklist, …) with `params.leg_b`

### `evaluate daily-strategy eval-bundle --strategy s6`

- **Required**: `--strategy s6`, `--start`, `--end`, symbol source as for other strategies, **`--leg-b`**
- **Behavior**: Delegates to `run_strategy_merit_bundle` with `pair_leg_b` set

## Preflight

- Mode `check` | `ensure`: for each leg A symbol, verify leg A and leg B exist in `stocks` and meet minimum bars / overlap rules for S6.

## Errors

- Typer exit **1** if `s6` / `eval-bundle` missing `--leg-b` when required.
- Preflight exit **2** after `--ensure-data` if still insufficient (unchanged from spec 019).
