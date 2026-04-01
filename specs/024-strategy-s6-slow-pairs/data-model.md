# Data model: 024 — S6 slow pairs

No new **database tables**. All inputs are existing relational entities.

## Logical entities (in-memory / JSON)

### `AlignedPairSeries`

| Field | Type | Description |
|-------|------|-------------|
| `dates` | `list[date]` | Strictly ascending common trading dates with valid positive closes for both legs |
| `log_a` | `list[float]` | Natural log of leg A close |
| `log_b` | `list[float]` | Natural log of leg B close |

**Validation**: `len(dates) == len(log_a) == len(log_b)`; all closes > 0 before log.

### `S6WindowSample` (code dataclass)

Same structural pattern as S3/S5: `regime_returns`, `baseline_returns`, `counts` keyed by regime bucket id (`q0`… from `s3_bucket_keys`) and horizon string.

### Persistence (`daily_strategy_merit_runs`)

Reuses existing JSON blob; `report_kind` values `s6_merit_report`, `s6_merit_report_rolling`. Params embed `leg_b` and `s6_*` windows.
