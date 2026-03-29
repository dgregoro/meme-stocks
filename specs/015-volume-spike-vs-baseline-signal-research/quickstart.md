# Quickstart: Volume spike research

## Prerequisites

- SQLite DB with `price_data` and `stocks` populated for symbols of interest.
- From repo root: `python -m backend.app.cli` with working `PYTHONPATH` or project venv.

---

## Critical: use the same DB as the API

An **empty** or **wrong** SQLite file produces **all-zero** backfills and evaluations. That does **not** mean the signal is dead; it means you never hit real data.

1. **Find the DB the API actually uses**

   **Containerized backend** (adjust name if yours differs):

   ```bash
   podman exec -it meme-stocks-backend /bin/sh -lc 'echo "$DATABASE_URL"'
   podman exec -it meme-stocks-backend /bin/sh -lc 'ls -la /app/data 2>/dev/null | head -50'
   ```

   **Local / same shell as uvicorn**:

   ```bash
   echo "$DATABASE_URL"
   ```

2. **Confirm tables have rows** (path below must match `DATABASE_URL`; see sanity script in §Sanity check).

You need one DB that has `stocks`, `price_data`, and—after backfill—`volume_spike_events`. A repo-local `deployment/data/app.db` with **0** stocks and **0** price rows is the **wrong** target unless your API is configured to use it **and** you have ingested prices into it.

---

## Backfill events

```bash
python -m backend.app.cli backfill volume-spike \
  --start 2024-01-01 --end 2024-06-30
```

**Against the same DB as deployment** (loads `deployment/.env`):

```bash
set -a && . deployment/.env && set +a
python -m backend.app.cli backfill volume-spike \
  --start 2025-02-01 --end 2026-03-20 \
  --replace-range
```

**Inside Podman** (same DB the container uses):

```bash
podman exec meme-stocks-backend \
  python -m backend.app.cli backfill volume-spike \
  --start 2025-02-01 --end 2026-03-20 \
  --replace-range
```

Optional:

- `--symbols AAPL,MSFT` — comma-separated; default: all stocks in `stocks` table.
- `--replace-range` — delete existing `volume_spike_events` in `[start,end]` before insert.

---

## Evaluate (CLI)

Long windows: evaluation loads at most **`limit`** events (default **500**). Use **`--limit 2000`** (API cap) so summaries are not silently truncated.

```bash
python -m backend.app.cli evaluate volume-spike \
  --start 2025-02-01 --end 2026-03-20 \
  --limit 2000
```

**Podman**:

```bash
podman exec meme-stocks-backend \
  python -m backend.app.cli evaluate volume-spike \
  --start 2025-02-01 --end 2026-03-20 \
  --limit 2000
```

---

## API (read-only)

**Query parameters are `since_date` and `until_date`**, not `start` / `end`.

With API running (`uvicorn backend.app.main:app`):

```bash
curl -s "http://127.0.0.1:8000/api/volume-spike/evaluation/summary?since_date=2025-02-01&until_date=2026-03-20&limit=2000" | jq .

curl -s "http://127.0.0.1:8000/api/volume-spike/evaluation/by-type?since_date=2025-02-01&until_date=2026-03-20&limit=2000" | jq .

curl -s "http://127.0.0.1:8000/api/volume-spike/evaluation/by-symbol?since_date=2025-02-01&until_date=2026-03-20&limit=25" | jq .

curl -s "http://127.0.0.1:8000/api/volume-spike/events?since_date=2026-01-01&until_date=2026-03-20&limit=20" | jq .
```

Other examples:

- `GET /api/volume-spike/events?symbol=AAPL&since_date=2024-01-01&until_date=2024-06-30`

---

## Sanity check (if you still see zeros)

Run against the **same** SQLite file `DATABASE_URL` points to. For `sqlite:///./data/app.db`, resolve the path from the process cwd; for `sqlite:////absolute/path`, use that path.

**Example** (adjust DB path for your container):

```bash
podman exec meme-stocks-backend python - <<'PY'
import os
import sqlite3

url = os.environ.get("DATABASE_URL", "")
if not url.startswith("sqlite"):
    print("Expected sqlite DATABASE_URL, got:", url)
    raise SystemExit(1)
rest = url.replace("sqlite:///", "", 1).split("?")[0]
if rest == ":memory:":
    print("In-memory DB; run counts inside the same process as the app.")
    raise SystemExit(1)
db_path = rest if rest.startswith("/") else os.path.abspath(os.path.join(os.getcwd(), rest))

print("DATABASE_URL", url)
print("resolved path", db_path)
conn = sqlite3.connect(db_path)
cur = conn.cursor()
for q in [
    "SELECT COUNT(*) FROM stocks",
    "SELECT COUNT(*) FROM price_data",
    "SELECT COUNT(*) FROM volume_spike_events",
]:
    try:
        print(q, "->", cur.execute(q).fetchone())
    except Exception as e:
        print(q, "->", e)
conn.close()
PY
```

If `stocks` or `price_data` counts are **0**, fix ingestion / `DATABASE_URL` before interpreting volume-spike results.

---

## How to judge (signal sniff test)

Only treat results as meaningful if:

- `total_events` is clearly above zero.
- At least one of `spike_up`, `spike_down`, or `spike_flat` has **decent `evaluable_count`** per horizon.
- One event type shows a **stable** pattern across **1d / 3d / 5d** (not a single-horizon blip).
- **`by-symbol`** is not dominated by a handful of tickers.

**Stop or pause** if all types are weak, counts are tiny, or a few symbols explain everything. If something survives, a reasonable next spec is **016-volume-spike-robustness-and-paper-simulation** (not ML first).

---

## Configuration (env)

See `config.py` — keys prefixed `volume_spike_research_*` (baseline window, statistic, ratio threshold, flat band, optional min close / min baseline volume, horizons).

---

## Expected checks (implementation)

1. Backfill twice without `--replace-range` does not duplicate `(symbol, event_date)` (upsert or unique violation handled).
2. Empty date range returns empty list / zero counts, HTTP 200 — not 500.
3. Horizons with insufficient future bars show `evaluable_count` lower than total events for that horizon.
