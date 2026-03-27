# API Contract: Leader-Follower Diagnostics (005 Extensions)

**Base path**: `/api/leader-follower`

**Purpose**: Document changes to diagnostics endpoints for the grouped leader universe feature. Extends existing observability contract.

---

## GET /status — Changes

### stage_counts (extended)

**New field**: `grouped_leader_universe_size` (int)

The number of distinct symbols in `stock_groups`. Only these symbols are eligible for leader detection during the bootstrap phase.

| Field | Type | Description |
|-------|------|-------------|
| input_universe_size | int | Total stocks (unchanged) |
| **grouped_leader_universe_size** | **int** | **NEW** — Distinct symbols in stock_groups; leader-eligibility set |
| leader_events_detected | int | Leaders found in grouped universe |
| follower_candidates_found | int | Unchanged |
| signals_emitted | int | Unchanged |

### empty_reason (extended)

**New value**: `stock_groups_empty`

Evaluation order for `empty_reason`:

1. `no_run` — No job run exists
2. `failed` — Run failed (success=false)
3. `stock_groups_empty` — `grouped_leader_universe_size == 0`; pipeline short-circuited before leader detection
4. `no_leaders` — Grouped universe non-empty but no leaders met thresholds
5. `no_candidates` — Leaders found but no follower candidates
6. `no_confirmations` — Candidates found but no signals after confirmation
7. `ok` — Signals emitted

### Response Example (with new field)

```json
{
  "last_run": { ... },
  "stage_counts": {
    "input_universe_size": 1601,
    "grouped_leader_universe_size": 30,
    "leader_events_detected": 2,
    "follower_candidates_found": 4,
    "signals_emitted": 0
  },
  "empty_reason": "no_confirmations"
}
```

When `stock_groups` is empty:

```json
{
  "stage_counts": {
    "input_universe_size": 1601,
    "grouped_leader_universe_size": 0,
    "leader_events_detected": 0,
    "follower_candidates_found": 0,
    "signals_emitted": 0
  },
  "empty_reason": "stock_groups_empty"
}
```

---

## GET /runs — metrics Extension

Each run's `metrics` object includes the new key:

| Key | Type | Description |
|-----|------|-------------|
| grouped_leader_universe_size | int | Distinct symbols in stock_groups for this run |

---

## GET /signals — diagnostics (when empty)

When `signals=[]`, the `diagnostics` block (if present) includes `stage_counts` with `grouped_leader_universe_size` and `empty_reason` per above.

---

## Backward Compatibility

- **grouped_leader_universe_size**: New field; default 0 when absent (older runs)
- **empty_reason stock_groups_empty**: New value; clients that do not recognize it can treat it as a variant of "no leaders" for display purposes
