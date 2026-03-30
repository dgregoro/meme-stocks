# Contracts: 020 Shared research execution

## JSON: `ResearchRunEnvelope`

Emitted by `ResearchRunEnvelope.to_json_dict()`:

```json
{
  "run_kind": "string",
  "strategy_family": "string",
  "eval_start": "YYYY-MM-DD",
  "eval_end": "YYYY-MM-DD",
  "universe_label": "string",
  "symbol_count": 0,
  "symbols_fingerprint_sha256_16": "hex16",
  "cost_round_trip_bps": 10.0,
  "git_sha_or_version": "string or null",
  "notes": "string or null"
}
```

## CLI (future / planned)

| Command | Contract |
|---------|----------|
| `research backtest daily-simple` | **Planned** — flags: `--symbols-file`, `--start`, `--end`, `--horizon-days`, `--entry`, `--cost-bps`; stdout JSON with `gross`/`net` series keys per `net-metrics-reporting.md` |
| `research walk-forward run` | **Planned** — `--windows calendar|trading`, `--splits N`, callback target TBD |

## JSON: `daily_simple_result_to_jsonable`

Summary dict: **percentage points** for all `*_return_pct_*`, `cumulative_return_pct_*`, `final_cumulative_return_pct_*`, `max_drawdown_pct_*`; `cost_round_trip_bps` and `cost_model` per slice. `period_trade_return_pct_*` lists match completed trades in order. See `research_execution.daily_simple_backtest`.

## Internal Python contracts

- **Costs**: inputs are **percentage points** on simple returns (`float`).
- **Splits**: `split_calendar_range` raises `ValueError` if `start > end`.
- **Harness** (planned): callback signature `(window_start, window_end) -> dict` with optional `error` key.

## Versioning

- Envelope fields are additive-only; removing fields requires spec version bump and migration notes.
