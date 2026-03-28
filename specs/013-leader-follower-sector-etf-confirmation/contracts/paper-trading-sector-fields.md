# Contract: Paper trade sector fields (API)

`GET /api/leader-follower/paper-trading/{run_id}` returns `trades[]` with **additive** optional fields on each trade:

| Field | Type | Description |
|-------|------|-------------|
| `sector_etf_symbol` | string \| null | ETF ticker |
| `sector_close` | number \| null | Sector close on entry date |
| `sector_ma` | number \| null | Prior-window MA when applicable |
| `sector_rolling_return_pct` | number \| null | Window return % when applicable |
| `sector_confirmation_passed` | boolean \| null | True when trade executed under gate |

Omitted on old rows → null.

Run summary unchanged except existing `skipped_count` includes sector skips; config JSON may list sector keys.
