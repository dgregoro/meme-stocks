# Quickstart: Leader-Follower API Observability

**Feature**: 004-leader-follower-api-observability

## Overview

Read-only APIs for debugging and evaluating the leader-follower signal pipeline. Use these endpoints to determine why `GET /api/leader-follower/signals` returns empty, inspect intermediate stages, and validate detection logic.

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/leader-follower/status` | One-stop diagnostic: last run, stage counts, empty_reason |
| `GET /api/leader-follower/runs` | Recent job runs with full metrics |
| `GET /api/leader-follower/leader-events` | Recent detected leaders |
| `GET /api/leader-follower/follower-candidates` | Recent follower candidates |
| `GET /api/leader-follower/signals` | Final signals; when empty, includes diagnostics |

## Quick Debugging Flow

1. **Check status** — `GET /api/leader-follower/status`
   - If `empty_reason: "no_run"` → Job has not run or scheduler is off
   - If `empty_reason: "failed"` → Check `last_run.error_message`
   - If `empty_reason: "no_leaders"` → Price/volume thresholds not met
   - If `empty_reason: "no_candidates"` → Leaders found but no group members passed filter
   - If `empty_reason: "no_confirmations"` → Candidates found but all filtered (e.g., cooldown)

2. **Inspect runs** — `GET /api/leader-follower/runs?limit=10`
   - View recent runs with `metrics` (input_universe_size, leader_events_detected, etc.)

3. **Inspect leader events** — `GET /api/leader-follower/leader-events?limit=20`
   - Verify which symbols qualified as leaders

4. **Inspect follower candidates** — `GET /api/leader-follower/follower-candidates?limit=20`
   - See which (leader, follower) pairs were candidates

5. **Signals with diagnostics** — `GET /api/leader-follower/signals`
   - When empty, response includes `diagnostics` with `empty_reason` and `stage_counts`

## Example: Why Are There No Signals?

```bash
# 1. One call for diagnosis
curl http://localhost:8000/api/leader-follower/status

# Example response when no leaders found:
# {"last_run": {...}, "stage_counts": {"input_universe_size": 25, "leader_events_detected": 0, ...}, "empty_reason": "no_leaders"}
```

## Authentication

Same as other `/api/*` endpoints. No special auth.

## Preconditions

- Leader-follower job must be enabled (`leader_follower_enabled=true` in config).
- Job runs after price collection; ensure `price_data` has recent rows.
- `stock_groups` must be populated for follower candidate selection.
