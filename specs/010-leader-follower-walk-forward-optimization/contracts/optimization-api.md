# API Contract: Leader-Follower Optimization (read-only)

Base path: `/api/leader-follower/optimization`

All responses use JSON. Errors: structured `detail` per PRD Appendix C (`error_detail` helper).

## GET `/runs`

**Purpose**: List recent optimization runs.

**Query parameters**:

| Name | Type | Default | Notes |
|------|------|---------|--------|
| `limit` | int | 50 | 1–200 |

**Response 200**:

```json
{
  "runs": [
    {
      "id": 1,
      "created_at": "2026-03-24T12:00:00+00:00",
      "train_start": "2025-02-01",
      "train_end": "2025-10-31",
      "validate_start": "2025-11-01",
      "validate_end": "2026-01-31",
      "test_start": null,
      "test_end": null,
      "ranking_method": "walk_forward_v1",
      "result_count": 24
    }
  ]
}
```

---

## GET `/{run_id}`

**Purpose**: Full run metadata for inspection / reproducibility.

**Response 200**: run fields plus parsed `config_json` as object:

```json
{
  "id": 1,
  "created_at": "...",
  "train_start": "...",
  "train_end": "...",
  "validate_start": "...",
  "validate_end": "...",
  "test_start": null,
  "test_end": null,
  "ranking_method": "walk_forward_v1",
  "config": { }
}
```

**Response 404**: `NOT_FOUND` if run does not exist.

---

## GET `/{run_id}/top-results`

**Purpose**: Top N parameter sets by stored rank.

**Query parameters**:

| Name | Type | Default | Notes |
|------|------|---------|--------|
| `limit` | int | 20 | 1–100 |

**Response 200**:

```json
{
  "run_id": 1,
  "results": [
    {
      "rank": 1,
      "robustness_score": 1.23,
      "params": { },
      "train_metrics": { },
      "validate_metrics": { },
      "test_metrics": null
    }
  ]
}
```

**Response 404**: run not found.
