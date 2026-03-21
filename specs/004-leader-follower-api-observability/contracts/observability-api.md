# API Contract: Leader-Follower Observability

**Base path**: `/api/leader-follower`

**Purpose**: Read-only endpoints for debugging and evaluating the leader-follower pipeline. All endpoints return 200 on success; empty states are explicit and structured.

---

## GET /status

One-stop diagnostic: last run summary, stage counts, and an explicit reason when no signals are present.

### Query Parameters

None.

### Response (200)

```json
{
  "last_run": {
    "run_id": 42,
    "run_at": "2026-03-21T17:00:00Z",
    "started_at": "2026-03-21T17:00:00Z",
    "duration_seconds": 2.3,
    "success": true,
    "error_message": null,
    "summary": "leader-follower: 3 leaders, 5 signals"
  },
  "stage_counts": {
    "input_universe_size": 25,
    "leader_events_detected": 3,
    "follower_candidates_found": 12,
    "signals_emitted": 5
  },
  "empty_reason": "ok"
}
```

When no run exists: `"last_run": null`, `"stage_counts": null`, `"empty_reason": "no_run"`.

When run failed: `"success": false`, `"error_message": "..."`, `"empty_reason": "failed"`.

When run succeeded but zero signals: `"empty_reason"` is one of `"no_leaders"`, `"no_candidates"`, `"no_confirmations"`, or `"ok"` (if counts indicate signals were emitted).

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| last_run | object \| null | Most recent run; null if never run |
| last_run.run_id | int | job_run_history.id |
| last_run.run_at | string | ISO 8601 |
| last_run.started_at | string | ISO 8601 |
| last_run.duration_seconds | float | Elapsed time |
| last_run.success | bool | Run completed without exception |
| last_run.error_message | string \| null | Present if failed |
| last_run.summary | string \| null | Truncated summary text |
| stage_counts | object \| null | From metrics_json; null if no run |
| empty_reason | string | One of: no_run, failed, no_leaders, no_candidates, no_confirmations, ok |

---

## GET /runs

Recent job runs with full metrics for the leader-follower detection job.

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| limit | int | 20 | Max runs (1–100) |

### Response (200)

```json
{
  "runs": [
    {
      "id": 42,
      "run_at": "2026-03-21T17:00:00Z",
      "started_at": "2026-03-21T17:00:00Z",
      "duration_seconds": 2.3,
      "success": true,
      "error_message": null,
      "summary": "leader-follower: 3 leaders, 5 signals",
      "metrics": {
        "input_universe_size": 25,
        "leader_events_detected": 3,
        "follower_candidates_found": 12,
        "signals_emitted": 5,
        "symbols_skipped": 0,
        "errors_count": 0
      }
    }
  ]
}
```

### Empty Result

When no runs: `{"runs": []}`.

---

## GET /leader-events

Recent detected leader events.

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| limit | int | 50 | Max results (1–200) |
| since_date | str | — | ISO date (YYYY-MM-DD); event_date >= since_date |
| leader | str | — | Filter by leader_symbol |
| run_id | int | — | Filter by job_run_id (FK to job_run_history) |

### Response (200)

```json
{
  "events": [
    {
      "id": 1,
      "leader_symbol": "GME",
      "event_date": "2026-03-21",
      "return_pct": 8.5,
      "volume_ratio": 2.1,
      "direction": "up",
      "run_id": 42,
      "created_at": "2026-03-21T17:00:05Z"
    }
  ]
}
```

### Empty Result

When no events match: `{"events": []}`.

---

## GET /follower-candidates

Recent follower candidates from `leader_follower_candidates` table (populated during `run_detection`).

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| limit | int | 50 | Max results (1–200) |
| since_date | str | — | ISO date; filter by event_date |
| leader | str | — | Filter by leader symbol |
| follower | str | — | Filter by follower symbol |
| run_id | int | — | Filter by job_run_id |

### Response (200)

```json
{
  "candidates": [
    {
      "leader_symbol": "GME",
      "follower_symbol": "AMC",
      "event_date": "2026-03-21",
      "group_id": "meme",
      "run_id": 42,
      "metrics": {},
      "created_at": "2026-03-21T17:00:06Z"
    }
  ]
}
```

Metrics object (from metrics_json) may contain optional screening/lag fields (e.g., follower_return_pct at event_date); structure is extensible.

### Empty Result

When no candidates: `{"candidates": []}`.

---

## GET /signals (Enhanced)

Existing endpoint enhanced with diagnostics when signals are empty.

### Query Parameters

Unchanged: `limit`, `since_date`, `leader`, `group`.

### Response (200) – With Signals

```json
{
  "signals": [ /* existing signal items */ ]
}
```

### Response (200) – Empty With Diagnostics

When no signals match, always add `diagnostics` (regardless of filters):

```json
{
  "signals": [],
  "diagnostics": {
    "last_run_id": 42,
    "last_run_at": "2026-03-21T17:00:00Z",
    "stage_counts": {
      "input_universe_size": 25,
      "leader_events_detected": 0,
      "follower_candidates_found": 0,
      "signals_emitted": 0
    },
    "empty_reason": "no_leaders"
  }
}
```

When no run exists: `diagnostics` may have `last_run`: null and `empty_reason`: "no_run". Diagnostics block is always present when signals is empty.

### Error Responses

- **400**: Invalid query params
- **500**: Server error (structured per PRD Appendix C)
