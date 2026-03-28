# Quickstart: 014 Regime filtering (research)

## Preconditions

- Stocks: benchmark (default **SPY**) has **daily** bars in `price_data` overlapping simulation windows.
- Leader-follower signals and follower prices present (same as 011/013).

## Single simulation (CLI, after implementation)

Example: enable regime filter with uptrend + low vol:

```bash
export DATABASE_URL=sqlite:////path/to/app.db
export PYTHONPATH=/path/to/meme-stocks

python -m backend.app.cli simulate leader-follower \
  --start 2025-02-01 --end 2026-03-20 \
  --entry next_open --holding_days 3 --max_positions_per_event 1 \
  --cost_pct 0.1 \
  --regime-filter \
  --regime-benchmark SPY \
  --market-trend-window 20 \
  --require-market-uptrend \
  --volatility-window 10 \
  --volatility-threshold 0.02 \
  --require-low-volatility
```

*(Exact flag names follow implementation; if CLI lags, use persisted configs via API or temporary JSON merge in research.)*

## Walk-forward grid snippet

```json
{
  "base_config": {
    "entry_mode": "next_open",
    "exit_mode": "fixed_days",
    "per_trade_cost_pct": 0.1,
    "regime_benchmark_symbol": "SPY"
  },
  "grid": {
    "holding_days": [3, 5],
    "regime_filter_enabled": [false, true],
    "require_market_uptrend": [true],
    "require_low_volatility": [false, true],
    "market_trend_window": [20],
    "volatility_window": [10],
    "volatility_threshold": [0.015, 0.02]
  },
  "ranking": {
    "method": "walk_forward_v1",
    "min_trades_validate": 5,
    "w_deg": 0.5,
    "w_dd": 0.25
  }
}
```

Keep grid **small**; `require_low_volatility` doubles branches—watch combination caps.

## Rolling robustness

Use the same keys in `grid` with `"ranking": { "method": "rolling_robustness_v1", ... }` per `012` loader.

## Interpretation

- Compare **median split returns**, **worst split**, **fraction positive**, and **trade count** between `regime_filter_enabled: false` vs `true` paired configs.
- **Sector + regime**: set `sector_confirmation_enabled: true` and `regime_sector_strength_required: true` only when both are intended.
