# Implementation Plan: 024 — S6 slow pairs

## Technical context

- **Stack**: Python 3.11+, FastAPI ecosystem; existing `daily_frequency_strategy_research` patterns (S1–S5).
- **Data**: `price_data` daily OHLCV for two symbols; optional use of `get_settings().research_default_round_trip_cost_bps` for docs / envelope.
- **Unknowns (resolve in research phase)**: beta estimation method (rolling OLS vs static), spread units (simple diff vs log), delisting / missing-bar policy.

## Phases

1. **Design**: Pair evaluation window, z thresholds from `config.py`, structured errors on insufficient overlap.
2. **Core**: `s6_*` settings; `_compute_s6_window_sample` + `run_s6_evaluation`; merit pooling if multi-pair list is in scope.
3. **CLI / persistence**: Mirror S5 registration; preflight ensures both legs have bars.
4. **Tests**: unit tests for spread/z logic and one DB-backed happy path.

## Constitution / reliability

- No silent external calls; pair research is read-only DB.
- Explicit hints when overlap or history is insufficient (PRD §5.0).
