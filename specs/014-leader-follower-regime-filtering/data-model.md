# Data model: 014 Leader-follower regime filtering

## PaperTradingConfig (extensions)

New fields (flattened JSON with existing leader-follower paper keys):

| Field | Type | Default | Notes |
|-------|------|---------|--------|
| `regime_filter_enabled` | bool | `false` | Master switch |
| `regime_benchmark_symbol` | str | `"SPY"` | Must exist in `price_data` for gate to pass |
| `market_trend_window` | int | `20` | Trading days for MA; must be ≥ 1 when uptrend required |
| `require_market_uptrend` | bool | `true` | If true, close > MA(window) on decision date |
| `volatility_window` | int | `10` | Trading days for std of returns; must be ≥ 2 if vol check active |
| `volatility_threshold` | float | `0.02` | Max allowed std of simple daily returns (decimal) |
| `require_low_volatility` | bool | `false` | If false, skip volatility clause in allow_trade |
| `regime_sector_strength_required` | bool | `false` | If true, `sector_confirmation_enabled` must be true |

**Validation**

- If `regime_sector_strength_required` and not `sector_confirmation_enabled` → error.
- Windows ≤ 0 invalid; `volatility_window` must allow at least one return if `require_low_volatility`.

## PaperSimulationMetrics

Add:

| Field | Type | Description |
|-------|------|-------------|
| `skipped_regime_filter_count` | int | Signals that would trade but blocked by regime |

`skipped_count` total **includes** regime skips (consistent with 013 sector skips).

## LeaderFollowerPaperRun (ORM)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `skipped_regime_filter_count` | Integer | no | `0` |

## LeaderFollowerPaperTrade (ORM)

Nullable columns (additive migration), aligned with API contract:

| Column | Type | Description |
|--------|------|-------------|
| `regime_benchmark_symbol` | String | Benchmark used |
| `regime_decision_date` | Date | Same as entry date unless spec changes |
| `regime_benchmark_close` | Float | Close on decision date |
| `regime_benchmark_ma` | Float | MA value (prior window) |
| `regime_market_uptrend_passed` | Boolean | Null if rule not required |
| `regime_volatility` | Float | Rolling std of returns |
| `regime_low_volatility_passed` | Boolean | Null if rule not required |
| `regime_sector_strength_passed` | Boolean | Null if `regime_sector_strength_required` false |
| `regime_filter_passed` | Boolean | Overall allow |

*Implementation may collapse some booleans into JSON if project prefers single `regime_context_json`—spec prefers **explicit columns** for queryability (match 013 style).*

## Optimization / robustness

- `leader_follower_optimization_results` / split results: `train_metrics_json`, `validate_metrics_json`, `test_metrics_json` gain `skipped_regime_filter_count` inside metric blobs when present.
- Grid keys listed in `plan.md` / walk-forward `ALLOWED_GRID_KEYS`.

## Relationships

- No new FKs. Trades reference existing `run_id`; regime data is **denormalized** on each trade row.
