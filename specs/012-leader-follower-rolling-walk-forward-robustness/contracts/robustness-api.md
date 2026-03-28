# API contract: `/api/leader-follower/robustness`

Read-only JSON API; errors use PRD Appendix C shape via `error_detail` (`code`, `message`, `details`).

## `GET /runs`

**Query**: `limit` (1–200, default 50)

**Response 200**:

```json
{
  "runs": [
    {
      "id": 1,
      "created_at": "2026-03-24T12:00:00Z",
      "overall_start": "2024-01-01",
      "overall_end": "2025-12-31",
      "split_count": 4,
      "ranking_method": "rolling_robustness_v1",
      "split_result_row_count": 32,
      "aggregate_count": 8
    }
  ]
}
```

## `GET /{run_id}`

**Response 200**: run header + parsed `grid_config_json` as `config` object + summaries.

**Response 404**: `NOT_FOUND` — unknown run id.

## `GET /{run_id}/top-results`

**Query**: `limit` (1–100, default 20)

**Response 200**:

```json
{
  "run_id": 1,
  "results": [
    {
      "rank": 1,
      "robustness_score": 12.34,
      "params": {},
      "aggregate_metrics": {}
    }
  ]
}
```

## `GET /{run_id}/splits`

**Query**:

- `limit` (1–500, default 100)
- `offset` (≥ 0, default 0)
- `config_key` optional — SHA-256 hex matching `config_hash`
- `split_index` optional — 0-based

**Response 200**:

```json
{
  "run_id": 1,
  "items": [
    {
      "split_index": 0,
      "config_hash": "…",
      "params": {},
      "train_start": "2024-01-01",
      "train_end": "2024-06-30",
      "validate_start": "2024-07-01",
      "validate_end": "2024-08-31",
      "test_start": "2024-09-01",
      "test_end": "2024-09-30",
      "train_metrics": {},
      "validate_metrics": {},
      "test_metrics": null
    }
  ]
}
```
