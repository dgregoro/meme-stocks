# Quickstart: Leader Threshold Calibration and Bootstrap Debugging

**Feature**: 006-leader-threshold-calibration-and-bootstrap-debugging

## What Changed

Leader detection now exposes:
- Symbol-level evaluation data (return_pct, volume_ratio, rejection_reasons)
- Near-miss candidates (symbols that almost qualified)
- Bootstrap/debug mode with relaxed thresholds
- Multi-run inspection with date filters and near_miss_count

## Prerequisites

- Backend running with `LEADER_FOLLOWER_ENABLED=true`
- `stock_groups` seeded
- At least one leader-follower job run (triggered or scheduled)

## Verify the Feature

### 1. Trigger a run and get run_id

```bash
curl -X POST http://localhost:8000/api/jobs/leader-follower-detection
# Response: {"stats":{"run_id":619},...}
```

### 2. Inspect symbol-level evaluations

```bash
curl -s "http://localhost:8000/api/leader-follower/leader-debug?run_id=619" | jq .
```

**Expected**:
- `evaluations`: List of symbols with return_pct, volume_ratio, qualified_as_leader, rejection_reasons
- `rejection_reasons` from taxonomy: insufficient_bars, no_data_on_event_date, zero_avg_volume, below_return_threshold, insufficient_volume, error

### 3. Inspect near-miss leaders

```bash
curl -s "http://localhost:8000/api/leader-follower/leader-near-miss?run_id=619" | jq .
```

**Expected**:
- `near_misses`: Top symbols that failed by smallest margin
- Includes return_threshold and volume_threshold for context

### 4. Multi-run inspection with date filter

```bash
curl -s "http://localhost:8000/api/leader-follower/runs?since_date=2026-03-20&until_date=2026-03-22&limit=10" | jq .
```

**Expected**:
- Runs filtered by run_at date
- Each run's metrics may include `near_miss_count`, `debug_mode`

### 5. Enable debug mode

Set env and restart:

```bash
export LEADER_FOLLOWER_DEBUG_MODE=true
# Or in deployment/.env: LEADER_FOLLOWER_DEBUG_MODE=true
```

Trigger run, then check metrics:

```bash
curl -s "http://localhost:8000/api/leader-follower/runs?limit=1" | jq '.runs[0].metrics.debug_mode'
# Expected: true
```

## Troubleshooting

| Symptom | Check |
|---------|-------|
| 404 on leader-debug | run_id exists? Run from before this feature has no debug data |
| evaluations: [] | Run may have completed before evaluations were persisted; re-trigger job |
| All symbols insufficient_bars | Price data missing or sparse for grouped symbols |
| near_misses: [] with leaders=0 | All symbols failed on data issues (not thresholds); check leader-debug rejection_reasons |
| debug_mode not in metrics | Ensure LEADER_FOLLOWER_DEBUG_MODE=true before job runs |
