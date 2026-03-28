# Research: 014 Leader-follower regime filtering

## Decision: Benchmark symbol

**Chosen**: Configurable `regime_benchmark_symbol` with default **`SPY`**.
**Rationale**: SPY is liquid, almost always present in retail datasets, and matches common “market trend” intuition.
**Alternatives considered**: QQQ (tech-heavy), RSP (equal-weight)—defer to grid for advanced users later; MVP default SPY only in docs.

## Decision: Return definition for volatility

**Chosen**: **Simple daily returns**: \(r_t = \frac{P_t}{P_{t-1}} - 1\); rolling std is **population** standard deviation over `volatility_window` returns ending at \(t\) (decision date)—in Python, `statistics.pstdev` (ddof=0).
**Rationale**: Matches shipped implementation; interpretable; thresholds are unitless decimals (e.g. `0.015` ≈ 1.5% daily std scale).
**Alternatives considered**: Sample std (`statistics.stdev`)—differs slightly on small windows; log returns—different scale; document if switched.

## Decision: Volatility threshold units

**Chosen**: `volatility_threshold` is the **maximum allowed** value of **population std of simple daily returns** (unitless decimal, e.g. `0.02` for ~2% daily scale). **≤** means pass.
**Rationale**: Matches quant conventions; grid examples can use round numbers.
**Alternatives**: Annualized vol—rejected for MVP (extra confusion).

## Decision: Missing / insufficient benchmark data

**Chosen**: When `regime_filter_enabled` is **true**, insufficient history or missing bars → **do not open trade** (treat as **fail**), increment **regime skip counter**, log **warning** with symbol + date + reason.
**Rationale**: PRD §5.0—explicit, conservative; avoids trading blind in unknown regime.
**Alternatives**: Pass with warning—rejected for default (hides risk).

## Decision: `regime_sector_strength_required` when 013 sector confirmation is off

**Chosen**: **`PaperTradingConfig.from_json_dict`** (or validator) **raises** `ValueError` if `regime_sector_strength_required` is true while `sector_confirmation_enabled` is false (clear message).
**Rationale**: Avoid ambiguous “sector required” with sector pipeline disabled.
**Alternatives**: Auto-enable sector—rejected (hidden coupling).

## Decision: Evaluation order (sector vs regime)

**Chosen**: **Sector confirmation first** (013), then **regime filter** (014), when both enabled—consistent with “sector is local, regime is broad” and reuse sector snapshot on trade payload before regime snapshot.
**Rationale**: Trades failing sector never consume regime computation; easier reasoning in logs.
**Alternatives**: Regime first—acceptable; pick one and test.

## Decision: CLI parity

**Chosen**: Add Typer flags on `simulate leader-follower` analogous to 013: `--regime-filter/--no-regime-filter`, optional `--regime-benchmark`, `--market-trend-window`, `--require-market-uptrend`, `--volatility-window`, `--volatility-threshold`, `--require-low-volatility`, and optional sector-strength flag—or document JSON-only for MVP; **implementation tasks** prefer **full flag set** for research ergonomics.

## Decision: Grid key names

**Chosen**: Align with spec `data-model.md` (e.g. `regime_filter_enabled`, `regime_benchmark_symbol`, `market_trend_window`, `require_market_uptrend`, `volatility_window`, `volatility_threshold`, `require_low_volatility`, `regime_sector_strength_required`).
**Rationale**: Consistent with snake_case JSON elsewhere.
