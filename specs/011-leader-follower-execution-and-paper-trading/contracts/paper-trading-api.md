# API Contract: Leader-Follower Paper Trading

**Base path**: `/api/leader-follower/paper-trading`

All responses use structured JSON. Errors follow PRD Appendix C shape.

---

## GET /runs

List recent simulation runs.

**Query parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `limit` | int | 50 | Max rows (cap 200) |

**Response 200:**

```json
{
  "runs": [
    {
      "id": 1,
      "created_at": "2026-03-24T12:00:00+00:00",
      "start_date": "2025-02-01",
      "end_date": "2026-03-20",
      "total_trades": 42,
      "skipped_count": 3,
      "cumulative_return_pct": 2.5,
      "max_drawdown_pct": 1.2
    }
  ]
}
```

---

## GET /{run_id}

Run detail with summary and paginated trades.

**Query parameters:**

| Name | Type | Default |
|------|------|---------|
| `offset` | int | 0 |
| `limit` | int | 100 |

**Response 200:**

```json
{
  "id": 1,
  "created_at": "2026-03-24T12:00:00+00:00",
  "config": { },
  "start_date": "2025-02-01",
  "end_date": "2026-03-20",
  "total_trades": 42,
  "skipped_count": 3,
  "win_rate": 0.55,
  "avg_return_pct": 0.12,
  "cumulative_return_pct": 2.5,
  "max_drawdown_pct": 1.2,
  "trades": [ ],
  "trades_total": 42,
  "offset": 0,
  "limit": 100
}
```

**Response 404:** run not found — `{ "error": { "code": "NOT_FOUND", "message": "..." } }`

---

## POST /runs/simulate (optional)

If implemented, triggers a new run from body params. **MVP**: simulation only via CLI; API read-only. *(Amend if POST added later.)*

---

## GET /{run_id}/equity-curve

**Response 200:**

```json
{
  "run_id": 1,
  "points": [
    { "trade_index": 0, "equity": 1.001, "cumulative_return_pct": 0.1 }
  ]
}
```

`trade_index` is 0-based after each trade.

---

## POST /internal — not used

Live trading out of scope.
