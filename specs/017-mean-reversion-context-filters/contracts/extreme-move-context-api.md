# API: extreme-move context evaluation (017)

Read-only GETs. Same query filters as other evaluation endpoints: **`since_date`**, **`until_date`**, **`symbol`**, **`limit`** (max 2000).

## `GET /api/extreme-move/evaluation/by-magnitude`

Response: JSON object whose keys are magnitude buckets (`3-5`, `5-8`, `8+`, `other`, `unknown`). Each value has the same shape as `/evaluation/summary` (total_events, date_range, by_horizon, by_event_type, etc.) for events in that bucket.

## `GET /api/extreme-move/evaluation/by-volume`

Response: keys are volume buckets (`normal`, `high`, `extreme`, `unknown`).

## `GET /api/extreme-move/evaluation/by-magnitude-volume`

Response: keys are `"{magnitude}|{volume}"` (e.g. `5-8|high`, `8+|extreme`). Events with missing context use `unknown` for the missing dimension.

**Note:** Re-run `backfill extreme-move` after upgrade so persisted events include context fields; older rows appear under `unknown` buckets until backfilled.
