# Data Model: Leader Threshold Calibration and Bootstrap Debugging

**Feature**: 006-leader-threshold-calibration-and-bootstrap-debugging
**Date**: 2026-03-22

## 1. New Entity: leader_debug_evaluations

### Table: leader_debug_evaluations

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| job_run_id | INTEGER | No | FK to job_run_history.id |
| stock_symbol | TEXT | No | Symbol evaluated |
| return_pct | FLOAT | Yes | Computed return % (NULL if not computed, e.g. insufficient_bars) |
| volume_ratio | FLOAT | Yes | curr_volume/avg_volume (NULL if not computed) |
| qualified_as_leader | BOOLEAN | No | True if symbol qualified |
| rejection_reasons | TEXT | No | JSON array of reason codes, e.g. `["below_return_threshold"]` |
| metrics_json | TEXT | Yes | Optional extra: prev_close, curr_close, avg_volume, curr_volume |
| created_at | DATETIME | No | Insert timestamp |

**Indexes**:
- `ix_leader_debug_evaluations_job_run_id` on job_run_id (for leader-debug, leader-near-miss queries)
- Unique constraint: (job_run_id, stock_symbol) — one evaluation per symbol per run

**Rejection reason codes** (from spec):
- `insufficient_bars`
- `no_data_on_event_date`
- `zero_avg_volume`
- `below_return_threshold`
- `insufficient_volume`
- `error`

### Model: LeaderDebugEvaluation

```python
# backend/app/models/leader_debug_evaluation.py
class LeaderDebugEvaluation(Base):
    __tablename__ = "leader_debug_evaluations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_symbol: Mapped[str] = mapped_column(String, nullable=False)
    return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    qualified_as_leader: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rejection_reasons: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

## 2. Config Extensions

### backend/app/config.py

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| leader_follower_debug_mode | bool | False | Use relaxed thresholds when true |
| leader_return_threshold_pct_debug | float | 3.0 | Return threshold in debug mode (relaxed from 5.0) |
| leader_volume_spike_threshold_debug | float | 1.2 | Volume threshold in debug mode (relaxed from 1.5) |

Env: `LEADER_FOLLOWER_DEBUG_MODE`, `LEADER_RETURN_THRESHOLD_PCT_DEBUG`, `LEADER_VOLUME_SPIKE_THRESHOLD_DEBUG`

## 3. metrics_json Extension (job_run_history)

**New keys**:
- `near_miss_count` (int): Count of non-qualified symbols that had return_pct and volume_ratio (e.g. failed only on threshold)
- `debug_mode` (bool): True when run used debug thresholds

Example:
```json
{
  "input_universe_size": 2622,
  "grouped_leader_universe_size": 30,
  "leader_events_detected": 0,
  "follower_candidates_found": 0,
  "signals_emitted": 0,
  "near_miss_count": 8,
  "debug_mode": false
}
```

## 4. Migration

Add migration (or inline in database.py) to create `leader_debug_evaluations` table. Follow existing pattern (e.g. `_migrate_create_leader_follower_candidates`).

## 5. No Changes To

- `leader_events` — unchanged
- `leader_follower_signals` — unchanged
- `leader_follower_candidates` — unchanged
- `stock_groups`, `price_data`, `stocks` — unchanged
