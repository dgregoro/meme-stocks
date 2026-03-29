# Data model: Extreme move events

## Entity: `ExtremeMoveEvent` → `extreme_move_events`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PK, autoincrement |
| `symbol` | VARCHAR(16) | FK → `stocks.symbol`, indexed |
| `event_date` | DATE | indexed |
| `return_pct` | FLOAT | Close-to-close daily return (percent) |
| `event_type` | VARCHAR(32) | `extreme_up` \| `extreme_down`, indexed |
| `created_at` | DATETIME TZ | NOT NULL |

**Unique**: `(symbol, event_date)` — one event per symbol per day.

## Rules

- **return_pct** = (close\_event / close\_prev − 1) × 100, rounded like 015 (`round(..., 4)`).
- **extreme_up**: return_pct ≥ `extreme_move_up_threshold_pct`.
- **extreme_down**: return_pct ≤ −`extreme_move_down_threshold_pct`.
- If both (asymmetric): tie-break per **research.md**.
- Missing prior close or non-positive prior close: **no event**.

## State

Append-only facts; backfill **upserts** same `(symbol, event_date)`.
