# Getting Started

This guide walks you through setting up and running the Meme Stocks Trading Application locally.

## Prerequisites

- **Python 3.11+** (recommended)
- **Node.js 18+** (for frontend)
- **SQLite** (used via SQLAlchemy; no manual setup required)
- **Linux**: Fedora is the preferred distro for development (CI runs in Fedora containers)

## Option A: Containers (Recommended for Portability)

Run the app in containers. Backend code is baked into the image; rebuild to apply backend changes.

### Quick start

```bash
# Build and run backend (serves API + built frontend)
podman-compose up --build

# Or with Docker
docker compose up --build
```

- **App**: http://localhost:8000
- **API docs**: http://localhost:8000/docs
- To apply backend changes: `podman-compose up --build` (rebuild the image).

### Frontend development (HMR)

When editing the frontend, use the Vite dev server for hot reload:

```bash
podman-compose --profile dev up --build
```

- **Frontend (HMR)**: http://localhost:5173
- **Backend API**: http://localhost:8000

### Production (portable image)

Run the built image without volume mounts:

```bash
podman build -t meme-stocks:latest .
podman run -p 8000:8000 -v meme-stocks-data:/app/data meme-stocks:latest
```

Data persists in the `meme-stocks-data` volume.

### Optional environment file (containers)

The stack may load `deployment/.env` for **optional** settings (e.g. `DATABASE_URL`, Alpaca keys if you use intraday). **Reddit API credentials are not used**—the app no longer ingests Reddit. Copy the example and adjust as needed:

```bash
cp deployment/.env.example deployment/.env
# Edit deployment/.env only if you need non-default paths or provider keys
```

---

## Option B: Local Setup (No Containers)

### Backend Setup

#### 1. Install dependencies

From the project root:

```bash
pip install -r backend/requirements.txt
```

#### 2. Configure environment (optional)

Defaults work for local dev. Create `.env` at project root if you want logging paths, DB URL, scheduling tweaks, or provider keys (**Alpaca** for intraday when enabled). Config loads from cwd; tests do not use your root `.env`.

```bash
LOG_LEVEL=INFO
LOG_FILE=logs/app.log   # yfinance/pandas noise saved here, not printed to terminal
DATABASE_URL=sqlite:///./data/app.db

# Scheduling (optional, defaults shown)
PRICE_COLLECTION_INTERVAL_MINUTES=15
NOTIFICATION_CHECK_INTERVAL_MINUTES=30
DAILY_ANALYSIS_HOUR=16
ENABLE_CATCH_UP=true
```

#### 3. Run tests

```bash
python -m pytest backend/tests/ -v
```

#### 4. Start the API

```bash
uvicorn backend.app.main:app --reload
```

The server starts at `http://127.0.0.1:8000`. Visit `/health` to confirm it's running.

### Frontend Setup

#### 1. Install dependencies

```bash
cd frontend
npm install
```

#### 2. Configure API base (optional)

Defaults to `http://127.0.0.1:8000`. To override, create `frontend/.env`:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

#### 3. Run dev server

```bash
npm run dev
```

Open the printed URL (default `http://localhost:5173`).

---

## Background Jobs

The application runs automated background jobs on a schedule:

- **Price Collection**: Updates price data for tracked stocks (default: every 15 minutes)
- **Daily Analysis**: Generates end-of-day analysis (default: 4 PM local)
- **Notification Checks**: Scans for unusual activity (default: every 30 minutes)
- **Leader-Follower Detection** (when `LEADER_FOLLOWER_ENABLED=true`): Detects leaders and follower candidates (default: 5 PM)
- **Intraday ingestion** (when `INTRADAY_INGESTION_ENABLED=true` and Alpaca is configured): Minute-bar fetch on its own interval

The product **used to** run **Reddit collection** on a schedule; that job and API surface **are removed**. **Catch-up**: On startup (e.g., after laptop sleep), the app can run missed jobs when `ENABLE_CATCH_UP=true`. Intervals are set via environment variables (see `backend/app/config.py`).

**Stock groups bootstrap**: Leader-follower detection needs `stock_groups` populated to produce follower candidates. If empty, the job detects leaders but emits zero candidates. See [Stock Groups Bootstrap](STOCK_GROUPS_BOOTSTRAP.md) for how to seed: `python -m backend.app.cli seed stock-groups`.

### Research recipes (YAML)

You can orchestrate repeated CLI sequences (e.g. backfill then evaluate) with **`python -m backend.app.cli research recipe run <file.yaml>`**. See **[specs/018-hypothesis-research-recipe/quickstart.md](../specs/018-hypothesis-research-recipe/quickstart.md)**.

---

## Configuration Reference

All settings are in `backend/app/config.py`. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `DATABASE_URL` | `sqlite:///./data/app.db` | SQLite database path |
| `PRICE_COLLECTION_INTERVAL_MINUTES` | `15` | Price update interval |
| `NOTIFICATION_CHECK_INTERVAL_MINUTES` | `30` | Notification scan interval |
| `DAILY_ANALYSIS_HOUR` | `16` | Hour (24h) for daily analysis |
| `ENABLE_CATCH_UP` | `true` | Run missed jobs on startup |
| `CORS_ALLOWED_ORIGINS` | `http://127.0.0.1:5173,...` | Allowed frontend origins |
| `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY` | — | Optional; required for intraday when enabled |
| `INTRADAY_INGESTION_ENABLED` | `false` | When `true`, scheduler runs intraday bar ingestion |

See `backend/app/config.py` for the full list (leader-follower, volume spike, SEC user-agent, and research-related settings).

---

## Development

### Running tests

```bash
# All tests
python -m pytest backend/tests/ -v

# Specific test file
python -m pytest backend/tests/test_scheduler_service.py -v
```

The suite covers configuration, repositories, external services, analysis logic, API endpoints, and the scheduler.

### Pre-commit hooks

Install and enable:

```bash
pip install pre-commit
pre-commit install
```

Run manually:

```bash
pre-commit run --all-files
```

Hooks include black, flake8, mypy, and core checks (large files, merge conflicts, whitespace).

### Guidelines

- **Follow `PLAN.md`** for milestones and scope
- **No silent failures**: Prefer explicit exceptions and clear error responses
- **Keep business logic in services**, not in API route handlers
- **Always add/update tests** when changing backend logic
- **Use timezone-aware datetimes**: `datetime.now(timezone.utc)`, not `datetime.utcnow()`
