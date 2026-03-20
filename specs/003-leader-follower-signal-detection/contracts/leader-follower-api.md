# API Contract: Leader-Follower Signals

**Base path**: `/api/leader-follower`

---

## GET /signals

List follower opportunity signals with optional filters.

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| limit | int | 50 | Max results (1–500) |
| since_date | str | — | ISO date (YYYY-MM-DD); filter signals with signal_date >= since_date |
| leader | str | — | Filter by leader_symbol |
| group | str | — | Filter by group_id |

### Response (200)

```json
{
  "signals": [
    {
      "id": 1,
      "leader_symbol": "GME",
      "follower_symbol": "AMC",
      "group_id": "meme",
      "signal_date": "2026-03-18",
      "strength_score": 0.72,
      "leader_return_pct": 8.5,
      "leader_volume_ratio": 2.1,
      "metrics": {},
      "created_at": "2026-03-18T17:05:00Z"
    }
  ]
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| id | int | Signal ID |
| leader_symbol | string | Leader stock symbol |
| follower_symbol | string | Follower stock symbol |
| group_id | string | Group from stock_groups |
| signal_date | string | ISO date |
| strength_score | float | 0–1 |
| leader_return_pct | float | Denormalized |
| leader_volume_ratio | float | Denormalized |
| metrics | object | Optional extra (e.g. follower baseline) |
| created_at | string | ISO 8601 datetime |

### Error Responses

- **400**: Invalid query params (e.g. invalid date format)
- **500**: Server error (structured per PRD Appendix C)

### Empty Result

When no signals match: `{"signals": []}`
