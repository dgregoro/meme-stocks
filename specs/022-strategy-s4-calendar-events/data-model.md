# Data model: S4 (logical)

S4 does **not** add SQL tables. It derives labels from **existing** entities.

## Entities (existing)

| Entity | Role |
|--------|------|
| `stocks` | Symbol must exist for preflight / eval |
| `price_data` | Daily OHLCV; `date` drives calendar flags and forward returns |
| `daily_strategy_merit_run` | Optional persistence of merit/bundle JSON |

## Derived concepts (in memory / JSON only)

| Concept | Description |
|---------|-------------|
| **S4 signal day** | `trade_date` in `[eval_start, eval_end]` with at least one enabled flag true (OpEx week weekday, calendar month-end, calendar quarter-end) |
| **Bucket key** | `cal_abc` — see `s4_bucket_label()` in `s4_calendar_flags.py` |
| **Window sample** | `S4WindowSample`: per-bucket and baseline lists of forward returns by horizon |

## Validation rules

- If `not (s4_include_opex_week or s4_include_calendar_month_end or s4_include_quarter_end_calendar)`: assessment returns insufficient with explicit message; merit checklist includes failure.
- Minimum bars: `max(horizons) + 5` valid bars (aligned with `daily_strategy_min_valid_bars("s4")`).
