# Research: 024 — S6 slow pairs

## Decision: Log-price OLS hedge with causal windows

**Decision**: On each aligned trading day *t*, compute intercept *α* and slope *β* from OLS of `log(close_A)` on `log(close_B)` using exactly the prior `W` overlapping observations *t−W … t−1*. Define spread residual `s_t = log(close_A,t) − α − β·log(close_B,t)`. Define rolling z-score using mean and population stdev of `s` over the prior `Z` residuals *t−Z … t−1* only; regimes via expanding quantiles on the z-series (`prior_expanding_quantile_regimes`).

**Rationale**: Matches textbook “cointegration-style” pair residual using prices; strict causality (no same-day leakage in beta or z moments). Reuses proven regime machinery from S3/S5.

**Alternatives considered**:

- **Fixed β** from full in-sample — rejected (lookahead).
- **Return spread** only — rejected for MVP (harder to interpret vs exploration doc’s price-level spread).
- **Ratio** without logs — rejected (scale issues for OLS).

## Decision: Forward outcome = leg A simple return

**Decision**: Forward horizons use **leg A** close-to-close returns from signal day *t* (same helper as other daily strategies) conditioned on pair z-regime at *t*.

**Rationale**: Single-symbol JSON shape stays consistent; leg B enters via spread construction only. Document that “pair PnL” can differ from leg-A-only; two-leg costs out of scope for MVP.

**Alternatives considered**:

- **Hedged return** (r_A − β r_B) — deferred (needs per-day β for return window).

## Decision: Merit shape = many legged‑A vs one leg B

**Decision**: `run_s6_merit_report(db, leg_a_symbols, eval_start, eval_end, *, leg_b)` pools like S5 but each skipped/skipped symbol is one leg A paired with fixed `leg_b`.

**Rationale**: Matches `--symbols A,B,C --leg-b SPY` operator workflow.

## Decision: Corporate actions

**Decision**: MVP uses **raw `price_data` closes** as stored; no split adjustment in this slice.

**Rationale**: Explicitly called out as limitation; avoids wrong adj factor without vendor adjustment tables.

## Decision: Config defaults

**Decision**: `s6_beta_window_days=60`, `s6_zscore_window_days=20`, `s6_regime_min_history_days=252`, `s6_regime_n_buckets=4`, `s6_load_buffer_calendar_days=400` (env-overridable via `Settings`).

**Rationale**: Align order-of-magnitude with S3/S5 research defaults; tune later.
