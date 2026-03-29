# API contract: `/api/extreme-move`

Read-only GET. Errors: structured (`error`, `error_type`, `message`, optional `details`). Date filters: **`since_date`**, **`until_date`** (not `start`/`end`).

## `GET /api/extreme-move/events`

Query: `symbol`, `since_date`, `until_date`, `event_type` (`extreme_up` | `extreme_down`), `limit` (default 100, max 2000), `offset`.

Response 200: `{ "events": [...], "total": N }` with event fields matching ORM.

## `GET /api/extreme-move/evaluation/summary`

Query: `since_date`, `until_date`, `symbol`, `limit` (max 2000).

Response: `total_events`, `date_range`, `forward_anchor`, `horizons_trading_days`, `by_horizon`, `by_event_type` (nested per type per horizon).

## `GET /api/extreme-move/evaluation/by-type`

Same filters; returns `{ "by_event_type": {...}, "forward_anchor", "horizons_trading_days" }`.

## `GET /api/extreme-move/evaluation/by-symbol`

Same filters plus `min_sample` (default 1). Returns `{ "symbols": [...], "min_sample" }`.

## Context buckets (017)

See `specs/017-mean-reversion-context-filters/contracts/extreme-move-context-api.md`:

- `GET /api/extreme-move/evaluation/by-magnitude`
- `GET /api/extreme-move/evaluation/by-volume`
- `GET /api/extreme-move/evaluation/by-magnitude-volume`

Event objects may include `magnitude_bucket`, `volume_ratio`, `volume_bucket` after a backfill with 017-aware code.
