# Quickstart: Grouped Leader Universe for Leader-Follower

**Feature**: 005-grouped-leader-universe-for-leader-follower

## What Changed

Leader-follower detection now restricts leader eligibility to symbols present in `stock_groups`. Previously, leaders were detected from the full stock universe (~1600 symbols), but follower candidates only came from grouped symbols—causing `follower_candidates_found: 0` when leaders were ungrouped (e.g. UMAC, SLS, PLAY).

## Prerequisites

- `stock_groups` seeded: `python -m backend.app.cli seed stock-groups`
- Backend running with `LEADER_FOLLOWER_ENABLED=true`

## Verify the Feature

### 1. Check stock_groups is populated

```bash
curl -s http://localhost:8000/api/stock-groups | jq '.is_empty, .total_rows'
```

Expect: `false` and `30` (or similar) after seeding.

### 2. Trigger leader-follower job

```bash
curl -X POST http://localhost:8000/api/jobs/leader-follower-detection
```

### 3. Inspect diagnostics

```bash
curl -s http://localhost:8000/api/leader-follower/status | jq .
```

**Expected when seeded:**

- `stage_counts.grouped_leader_universe_size` > 0 (e.g. 30)
- `stage_counts.input_universe_size` = full stocks count (e.g. 1601)
- `empty_reason` one of: `no_leaders`, `no_candidates`, `no_confirmations`, `ok`

**Expected when stock_groups empty:**

- `stage_counts.grouped_leader_universe_size` = 0
- `stage_counts.leader_events_detected` = 0
- `empty_reason` = `stock_groups_empty`

### 4. Compare before/after

Before this feature: leaders could be UMAC, SLS, PLAY (ungrouped) → 0 candidates.

After: only grouped symbols (NVDA, GME, AAPL, etc.) can become leaders → candidates possible when those symbols move.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| `grouped_leader_universe_size: 0` | Run `seed stock-groups` |
| `empty_reason: stock_groups_empty` | Same; seed and re-run job |
| `no_leaders` with grouped_universe > 0 | No grouped symbol met return/volume thresholds on event_date; check price data |
| `no_candidates` with leaders > 0 | Leaders found but group members moved beyond threshold or lack price data |

## Docs

See `docs/STOCK_GROUPS_BOOTSTRAP.md` for bootstrap design, seeding, and limitations.
