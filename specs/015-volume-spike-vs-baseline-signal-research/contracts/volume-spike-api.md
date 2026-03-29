# API contract: `/api/volume-spike`

All endpoints are **read-only** GET. Errors use structured body (`error`, `error_type`, `message`, optional `details`) per PRD Appendix C.

**Date filters:** use **`since_date`** and **`until_date`** (ISO `YYYY-MM-DD`). Parameters named `start` / `end` are **ignored** by FastAPI and will not filter results.

## `GET /api/volume-spike/events`

**Query parameters**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `symbol` | string | no | Filter ticker |
| `since_date` | date | no | `event_date >=` |
| `until_date` | date | no | `event_date <=` |
| `event_type` | string | no | `spike_up` \| `spike_down` \| `spike_flat` |
| `limit` | int | no | Default 100, max 2000 |
| `offset` | int | no | Pagination, default 0 |

**Response 200**

```json
{
  "events": [
    {
      "id": 1,
      "symbol": "AAPL",
      "event_date": "2024-03-15",
      "volume": 120000000,
      "baseline_volume": 35000000.0,
      "volume_ratio": 3.43,
      "same_day_return_pct": 0.62,
      "event_type": "spike_up",
      "created_at": "2026-03-27T12:00:00+00:00"
    }
  ],
  "total": 1
}
```

## `GET /api/volume-spike/evaluation/summary`

**Query parameters**: `since_date`, `until_date`, `symbol` (optional), `limit` (max events loaded for evaluation, default 500, cap 2000).

**Response 200**

```json
{
  "total_events": 100,
  "date_range": {"since": "2024-01-02", "until": "2024-06-28"},
  "forward_anchor": "event_date_close",
  "horizons_trading_days": [1, 3, 5],
  "by_horizon": {
    "1d": {
      "evaluable_count": 95,
      "win_rate": 0.52,
      "avg_return_pct": 0.15,
      "median_return_pct": 0.08
    }
  },
  "by_event_type": {
    "spike_up": {
      "1d": { "evaluable_count": 30, "win_rate": 0.5, "avg_return_pct": 0.1, "median_return_pct": 0.0 }
    }
  }
}
```

Missing forward prices: events omitted from that horizon’s stats; `evaluable_count` reflects this.

## `GET /api/volume-spike/evaluation/by-symbol`

Same filters as summary. Returns ranked list per symbol with per-horizon metrics and `event_count`.

## `GET /api/volume-spike/evaluation/by-type`

Aggregates keyed by `event_type` with per-horizon metrics (same shape as `by_event_type` in summary, possibly with totals).

## Error cases

| Status | When |
|--------|------|
| 400 | Invalid date or limit |
| 500 | DB errors (logged); message sanitized |
