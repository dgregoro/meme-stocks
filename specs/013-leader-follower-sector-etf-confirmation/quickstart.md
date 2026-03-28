# Quickstart: Sector ETF confirmation (013)

## Defaults

Sector gate is **off** (`sector_confirmation_enabled: false`). Behavior matches pre-013.

## Enable in simulation

Pass config via `simulate leader-follower` **JSON is embedded in code path** — extend `PaperTradingConfig` in Python or document future CLI `--config-json` if added.

For **optimization/robustness**, add to `base_config` or `grid`:

```json
{
  "base_config": {
    "sector_confirmation_enabled": true,
    "sector_trend_method": "ma_above",
    "sector_trend_window": 10,
    "minimum_sector_return_pct": 0.0,
    "require_positive_trend": true
  },
  "grid": {
    "holding_days": [3, 5],
    "sector_confirmation_enabled": [false, true]
  },
  "ranking": { "method": "walk_forward_v1", "...": "..." }
}
```

## ETF data

Mapped ETFs (e.g. SMH, XLK) must appear in **`stocks`** and have **daily `price_data`** for dates overlapping your simulation. Ingest like any symbol (same Yahoo pipeline).

## Static map

Edit `backend/app/data/stock_sector_etf_map.py` to add `STOCK_TO_SECTOR_ETF` entries.
