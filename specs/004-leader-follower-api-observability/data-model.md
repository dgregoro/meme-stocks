# Data Model: Leader-Follower API Observability

**Feature**: 004-leader-follower-api-observability
**Date**: 2026-03-21

## 1. Existing Entities (Modified)

### leader_events

**Change**: Add `job_run_id` (FK to `job_run_history`).

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | Integer | Not null, PK | Existing |
| leader_symbol | String(16), FK stocks.symbol | Not null | Existing |
| event_date | Date | Not null | Existing |
| return_pct | Float | Not null | Existing |
| volume_ratio | Float | Not null | Existing |
| direction | String(8) | Not null | Existing ('up' \| 'down') |
| **job_run_id** | Integer, FK job_run_history.id | Nullable (backfill) | **NEW** — Links event to run |
| created_at | DateTime(TZ) | Not null | Existing |

**Validation**: `job_run_id` required for new rows (created after this feature). Legacy rows may have NULL until backfilled (optional).

**Relationships**: `job_run_id` → `job_run_history.id`

---

### job_run_history

**No schema change.** Existing columns used:
- `id`, `job_name`, `run_at`, `started_at`, `duration_seconds`, `success`, `error_message`, `summary`, `metrics_json`

**Behavior change**: For `leader_follower_detection`, a row is inserted at job start (before `run_detection`); then updated on completion.

---

## 2. New Entity

### leader_follower_candidates

Stores follower candidates produced by `select_follower_candidates` during each run.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | Integer | Not null, PK, autoincrement | |
| job_run_id | Integer, FK job_run_history.id | Not null | Run that produced this candidate |
| event_date | Date | Not null | Same as leader event date |
| leader_symbol | String(16), FK stocks.symbol | Not null | Leader that triggered |
| follower_symbol | String(16), FK stocks.symbol | Not null | Candidate follower |
| group_id | String(64) | Not null | Group used for selection |
| metrics_json | Text | Nullable | Optional screening/lag metrics (JSON object) |
| created_at | DateTime(TZ) | Not null | Insert time |

**Indexes**: `job_run_id`, `event_date`, `leader_symbol`, `follower_symbol` (for filtering).

**Relationships**:
- `job_run_id` → `job_run_history.id`
- `leader_symbol`, `follower_symbol` → `stocks.symbol`
- Logical: candidate belongs to a leader event on `event_date` for `leader_symbol`; no FK to `leader_events` (optional future addition).

**Lifecycle**: Inserted during `run_detection` before `create_signals`. Read-only after creation.

---

## 3. Migration Notes

- **leader_events**: Add column `job_run_id INTEGER REFERENCES job_run_history(id)`. Existing rows: NULL allowed.
- **leader_follower_candidates**: New table. Alembic/raw migration.
- **job_run_history**: No migration; usage change only in scheduler.

---

## 4. metrics_json Shapes

### job_run_history.metrics_json (existing)

```json
{
  "input_universe_size": 25,
  "leader_events_detected": 3,
  "follower_candidates_found": 12,
  "signals_emitted": 5,
  "symbols_skipped": 0,
  "errors_count": 0
}
```

### leader_follower_candidates.metrics_json (new)

Extensible. Initially `{}` or `null`. Future examples:
```json
{
  "follower_return_pct": 0.5,
  "follower_volume_ratio": 1.0
}
```
