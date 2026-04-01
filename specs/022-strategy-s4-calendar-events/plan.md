# Plan: S4 calendar events (daily-frequency research)

## Approach

1. **Pure module** `backend/app/services/s4_calendar_flags.py` (already present): OpEx week, month-end, quarter-end, `s4_bucket_label`.
2. **Config** `s4_include_*` booleans in `config.py` (already present).
3. **Service** `daily_frequency_strategy_research.py`:
   - `S4WindowSample`, `_compute_s4_window_sample` (DailyBar + `compute_forward_return`)
   - `run_s4_evaluation`, `run_s4_merit_report`, `run_s4_merit_rolling_report`, `_rollup_s4_merit_rolling`
   - `assess_daily_strategy_symbol_data` + `daily_strategy_min_valid_bars` for `"s4"`
   - `run_strategy_merit_bundle` branch for `"s4"`
4. **CLI** `evaluate.py`: `s4`, `s4-merit`, `eval-bundle --strategy s4`.
5. **Persistence** `daily_strategy_merit_persistence.py`: `s4_*` report kinds.
6. **Catalog** `strategy_catalog.py`: S4 tooling = `implemented`, CLI hint.
7. **Tests**: `test_s4_calendar_flags.py`, extensions to existing daily-strategy tests.

## Dependencies

- None beyond existing price_data / stocks (no macro series).

## Risks

- **Calendar vs trading day:** month-end flag may fall on a non-trading day; bar may be absent → fewer events than naive calendar count (documented).
