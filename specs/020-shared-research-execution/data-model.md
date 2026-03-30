# Data model: 020 Shared research execution

## Implemented (code)

### `ResearchRunEnvelope` (in-memory / JSON)

| Field | Type | Notes |
|-------|------|--------|
| run_kind | str | e.g. `s1_merit_report`, `daily_simple_backtest_v1` |
| strategy_family | str | e.g. `s1`, `s2`, `generic` |
| eval_start | date | ISO in JSON |
| eval_end | date | ISO in JSON |
| universe_label | str | Human label for universe snapshot |
| symbol_count | int | Deduped uppercase symbols |
| symbols_fingerprint_sha256_16 | str | First 16 hex of SHA-256 of sorted symbol JSON array |
| cost_round_trip_bps | float | Assumption for interpretation |
| git_sha_or_version | str \| null | From `APP_VERSION` or `GIT_SHA` |
| notes | str \| null | Free text |

**Validation**: `from_json_dict` / `from_context` enforce types; symbol list normalized for fingerprint.

### Existing persistence (related)

| Table | Role |
|-------|------|
| `daily_strategy_merit_runs` | Full merit/bundle `report_json`; optional future `run_envelope` key inside JSON or new column |

## Planned entities (not yet in ORM)

### `DailySimpleBacktestRun` (conceptual)

- run_id, created_at, config_json (entry/exit, horizon, cost), symbols_fingerprint, equity_json or summary metrics — **only if** we persist backtests; v1 may be CLI-stdout-only.

### `WalkForwardHarnessRun` (conceptual)

- windows: list of `{start, end, child_run_ref or inline metrics}`
- errors per window

## Relationships

- Envelope **references** universe by label + fingerprint, not FK (universes may be file-based).
- Merit runs **may embed** envelope in JSON; no required foreign key to envelope table.
