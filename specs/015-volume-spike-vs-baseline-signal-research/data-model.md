# Data model: Volume spike events

## Entity: `VolumeSpikeEvent` → table `volume_spike_events`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | INTEGER | PK, autoincrement | |
| `symbol` | VARCHAR(16) | FK → `stocks.symbol`, indexed | |
| `event_date` | DATE | indexed | Spike trading day |
| `volume` | INTEGER | NOT NULL | Day volume |
| `baseline_volume` | FLOAT | NOT NULL | Mean or median over W prior days |
| `volume_ratio` | FLOAT | NOT NULL | `volume / baseline_volume` |
| `same_day_return_pct` | FLOAT | NOT NULL | `(close/close_prev - 1) * 100` |
| `event_type` | VARCHAR(32) | NOT NULL | `spike_up`, `spike_down`, `spike_flat` |
| `created_at` | DATETIME TZ | NOT NULL | Insert time |

**Unique constraint**: `(symbol, event_date)` — idempotent backfill via upsert/delete+insert or SQLite `ON CONFLICT` equivalent (SQLAlchemy merge or delete-in-range + insert).

**Relationships**: Optional logical link to `Stock`; no FK from other tables to events in MVP.

## Validation rules

- Baseline uses **W** consecutive prior **trading days** present in `price_data` only (same symbol). If fewer than W prior bars → skip day (no event).
- `baseline_volume` must be **> 0** before ratio; else skip.
- Event fires if `volume_ratio >= T` (config).
- `event_type` from same-day return vs ±ε% bands (config).

## State transitions

None — append-only facts; re-backfill same date replaces row (dedupe).

## Evaluation aggregates (not persisted)

- Per horizon: `evaluable_count`, `win_rate`, `avg_return_pct`, `median_return_pct`.
- Dimensions: global, `by_horizon`, `by_event_type`, `by_symbol` (where endpoint applies).
