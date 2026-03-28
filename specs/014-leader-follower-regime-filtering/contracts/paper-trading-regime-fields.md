# Contract: Paper trading API — regime fields (014)

**Scope**: Read models for leader-follower paper trading endpoints (`backend/app/api/leader_follower_paper_trading.py`).

## Run summary

Extend run list/detail DTOs with:

| Field | JSON key | Type | Notes |
|-------|-----------|------|--------|
| Skipped by regime | `skipped_regime_filter_count` | integer | ≥ 0 |

## Trade row

Extend paper trade DTOs with nullable fields:

| Field | JSON key | Type |
|-------|-----------|------|
| Benchmark symbol | `regime_benchmark_symbol` | string \| null |
| Decision date | `regime_decision_date` | date (ISO) \| null |
| Benchmark close | `regime_benchmark_close` | number \| null |
| Benchmark MA | `regime_benchmark_ma` | number \| null |
| Uptrend rule passed | `regime_market_uptrend_passed` | boolean \| null |
| Rolling volatility | `regime_volatility` | number \| null |
| Low-vol rule passed | `regime_low_volatility_passed` | boolean \| null |
| Sector strength passed | `regime_sector_strength_passed` | boolean \| null |
| Overall regime pass | `regime_filter_passed` | boolean \| null |

**Semantics**

- When `regime_filter_disabled` in stored config for that run, trade rows may have **all null** regime fields for rows created under pre-014 code; new rows with regime off: implementation may leave null or set `regime_filter_passed` true—consistent behavior documented in implementation.
- Errors: unchanged PRD Appendix C; **no** raw tracebacks.

## Versioning

Additive; existing clients ignore unknown fields.
