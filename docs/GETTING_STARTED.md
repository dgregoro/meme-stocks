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

### Reddit credentials

Create `deployment/.env` with your Reddit API credentials. The compose file loads it via `env_file`; tests do not load it, so CI passes without credentials.

```bash
cp deployment/.env.example deployment/.env
# Edit deployment/.env and add your keys
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

Defaults work for local dev. For Reddit data collection and custom settings, create `.env` at project root (config loads from cwd; tests do not use it):

```bash
LOG_LEVEL=INFO
LOG_FILE=logs/app.log   # yfinance/pandas noise saved here, not printed to terminal
DATABASE_URL=sqlite:///./data/app.db
REDDIT_CLIENT_ID=your-client-id
REDDIT_CLIENT_SECRET=your-client-secret
REDDIT_USER_AGENT=meme-stocks-app/0.1

# Scheduling (optional, defaults shown)
REDDIT_COLLECTION_INTERVAL_MINUTES=60
PRICE_COLLECTION_INTERVAL_MINUTES=15
NOTIFICATION_CHECK_INTERVAL_MINUTES=30
DAILY_ANALYSIS_HOUR=16
REDDIT_SUBREDDITS=wallstreetbets,stocks,investing
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

- **Reddit Collection**: Fetches recent posts from configured subreddits (default: hourly)
- **Price Collection**: Updates price data for tracked stocks (default: every 15 minutes)
- **Daily Analysis**: Generates end-of-day analysis (default: 4 PM)
- **Notification Checks**: Scans for unusual activity (default: every 30 minutes)
- **Leader-Follower Detection** (when `LEADER_FOLLOWER_ENABLED=true`): Detects leaders and follower candidates (default: 5 PM)

**Catch-up functionality**: On startup (e.g., after laptop sleep), the app checks for missed jobs and runs them automatically. Job intervals and subreddits are configurable via environment variables.

**Stock groups bootstrap**: Leader-follower detection needs `stock_groups` populated to produce follower candidates. If empty, the job detects leaders but emits zero candidates. See [Stock Groups Bootstrap](STOCK_GROUPS_BOOTSTRAP.md) for how to seed: `python -m backend.app.cli seed stock-groups`.

---

## Configuration Reference

All settings are in `backend/app/config.py`. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `DATABASE_URL` | `sqlite:///./data/app.db` | SQLite database path |
| `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | — | Required for Reddit data collection |
| `REDDIT_USER_AGENT` | `meme-stocks-app/0.1` | User agent for Reddit API |
| `REDDIT_COLLECTION_INTERVAL_MINUTES` | `60` | Reddit fetch interval |
| `PRICE_COLLECTION_INTERVAL_MINUTES` | `15` | Price update interval |
| `NOTIFICATION_CHECK_INTERVAL_MINUTES` | `30` | Notification scan interval |
| `DAILY_ANALYSIS_HOUR` | `16` | Hour (24h) for daily analysis |
| `REDDIT_SUBREDDITS` | `wallstreetbets,stocks,investing` | Subreddits to monitor |
| `ENABLE_CATCH_UP` | `true` | Run missed jobs on startup |
| `CORS_ALLOWED_ORIGINS` | `http://127.0.0.1:5173,...` | Allowed frontend origins |

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
