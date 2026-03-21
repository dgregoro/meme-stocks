# Quickstart: Leader-Follower Signal Detection

**Validation steps** after implementation.

---

## Prerequisites

- Backend running: `uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`
- `price_data` seeded for at least 2 symbols with 5+ days of data
- `stock_groups` table populated (seed script or manual INSERT)

---

## 1. Seed Test Data

```sql
-- Ensure stocks exist
INSERT OR IGNORE INTO stocks (symbol, name) VALUES ('GME', 'GameStop'), ('AMC', 'AMC Entertainment');

-- Seed stock_groups (group_id, stock_symbol)
INSERT INTO stock_groups (group_id, stock_symbol) VALUES ('meme', 'GME'), ('meme', 'AMC');

-- Seed price_data with a leader move: GME +6% with 2x volume on latest date
-- (Use PriceDataRepository or direct SQL; ensure 2+ days for return calc)
```

---

## 2. Enable Feature

Set in `.env` or environment:

```
LEADER_FOLLOWER_ENABLED=true
```

Restart backend. Job `leader_follower_detection` should be scheduled (CronTrigger hour=17 or configured hour).

---

## 3. Trigger Job (or Wait for Schedule)

- **Manual**: Call the job via scheduler API if exposed, or run `LeaderFollowerService.run_detection(db)` in a script.
- **Scheduled**: Wait for cron (e.g. 17:00) or advance system time in tests.

---

## 4. Verify Run Metrics

Query `job_run_history` for `leader_follower_detection`:

```sql
SELECT job_name, run_at, success, summary, metrics_json
FROM job_run_history
WHERE job_name = 'leader_follower_detection'
ORDER BY run_at DESC LIMIT 1;
```

Expect: `success=1`, `summary` like "leaders=N candidates=M signals=K", `metrics_json` with keys: input_universe_size, leader_events_detected, follower_candidates_found, signals_emitted.

---

## 5. Query API

```bash
curl -s "http://127.0.0.1:8000/api/leader-follower/signals?limit=10" | jq
```

Expect: `signals` array with at least one entry when GME moved and AMC did not (given seeded data).

---

## 6. Run Tests

```bash
pytest backend/tests/test_leader_follower_service.py backend/tests/test_leader_follower_api.py -v
```

---

## 7. Full Verification

```bash
./scripts/verify.sh
```
