# Data model: 013 Sector confirmation

## `LeaderFollowerPaperTrade` (extended)

| Column | Type | Notes |
|--------|------|--------|
| `sector_etf_symbol` | VARCHAR nullable | ETF used for check |
| `sector_close` | FLOAT nullable | Close on as_of |
| `sector_ma` | FLOAT nullable | MA of prior window (if method uses MA) |
| `sector_rolling_return_pct` | FLOAT nullable | Rolling return % (if method uses return) |
| `sector_confirmation_passed` | BOOLEAN nullable | True for persisted trades (always true) |

Legacy rows: all null / null passed.

## `PaperTradingConfig` (dataclass)

| Field | Type | Default |
|-------|------|---------|
| `sector_confirmation_enabled` | bool | False |
| `sector_trend_method` | enum string | `ma_above` |
| `sector_trend_window` | int | 10 |
| `minimum_sector_return_pct` | float | 0.0 |
| `require_positive_trend` | bool | True |
| `sector_etf_symbol` | str optional | None |

## `PaperSimulationMetrics` (extended)

| Field | Type | Notes |
|-------|------|--------|
| `skipped_sector_confirmation_count` | int | Skips due to failed or missing-data gate |
