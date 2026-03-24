# Contract: Leader Debug API

**Feature**: 006-leader-threshold-calibration-and-bootstrap-debugging
**Base path**: `/api/leader-follower`

## GET /api/leader-follower/leader-debug

Returns symbol-level evaluation data for a given run.

### Request

| Query param | Type | Required | Default | Description |
|-------------|------|----------|---------|-------------|
| run_id | int | Yes | — | Job run ID from job_run_history |
| limit | int | No | 50 | Max symbols to return (1–200) |

### Response 200

```json
{
  "run_id": 619,
  "event_date": "2026-03-22",
  "evaluated_count": 30,
  "leaders_count": 0,
  "evaluations": [
    {
      "symbol": "GME",
      "return_pct": 2.1,
      "volume_ratio": 1.3,
      "qualified_as_leader": false,
      "rejection_reasons": ["below_return_threshold", "insufficient_volume"]
    },
    {
      "symbol": "NVDA",
      "return_pct": null,
      "volume_ratio": null,
      "qualified_as_leader": false,
      "rejection_reasons": ["insufficient_bars"]
    }
  ]
}
```

### Empty state

- **404** when run_id does not exist
- **200** with `evaluations: []`, `evaluated_count: 0` when run has no debug data (e.g. run before this feature)

---

## GET /api/leader-follower/leader-near-miss

Returns top near-miss symbols for a run, ranked by proximity to qualifying.

### Request

| Query param | Type | Required | Default | Description |
|-------------|------|----------|---------|-------------|
| run_id | int | Yes | — | Job run ID |
| limit | int | No | 20 | Max symbols (1–100) |

### Response 200

```json
{
  "run_id": 619,
  "near_misses": [
    {
      "symbol": "GME",
      "return_pct": 4.2,
      "volume_ratio": 1.4,
      "rejection_reasons": ["below_return_threshold", "insufficient_volume"],
      "return_threshold": 5.0,
      "volume_threshold": 1.5
    }
  ]
}
```

Only includes symbols that were evaluated and have `return_pct` and `volume_ratio` (i.e. not insufficient_bars, no_data_on_event_date, zero_avg_volume, error). Ranked by proximity (closest to qualifying first).

### Empty state

- **404** when run_id does not exist
- **200** with `near_misses: []` when no near-miss data

---

## GET /api/leader-follower/runs (Extended)

Existing endpoint extended with:

### New query params

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| since_date | date | No | — | Filter runs on or after this date (run_at) |
| until_date | date | No | — | Filter runs on or before this date |

### Response (extended)

Each run item in `runs` array may include `near_miss_count` when available from metrics:

```json
{
  "runs": [
    {
      "id": 619,
      "run_at": "2026-03-22T19:09:26Z",
      "metrics": {
        "input_universe_size": 2622,
        "grouped_leader_universe_size": 30,
        "leader_events_detected": 0,
        "near_miss_count": 8,
        "debug_mode": false
      }
    }
  ]
}
```
