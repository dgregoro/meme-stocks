## Meme Stocks Trading Application

Backend service for analyzing meme stocks using Reddit sentiment and Yahoo Finance price data.

### Quickstart (backend)

1. Create and activate a virtualenv, then install dependencies:

```bash
cd backend
pip install -r requirements.txt
```

2. Run tests:

```bash
cd ..
python -m pytest
```

3. Start the API:

```bash
uvicorn backend.app.main:app --reload
```

Then open `http://127.0.0.1:8000/health` to confirm the service is running.

## Meme Stocks Trading Application

A Python backend for analyzing meme stocks using Reddit sentiment and price patterns.  
The project is organized around milestones defined in `PLAN.md` and aims to surface
unusual activity and trading signals for manual decision making (no live broker
integration).

### Features (planned & implemented)

- **Social sentiment analysis**: Reddit data (posts, engagement) and simple
  keyword‑based scoring.
- **Price pattern analysis**: Historical price data from Yahoo Finance with
  basic technical indicators.
- **Unusual activity detection**: Volume spikes, price moves, and sentiment shifts.
- **Paper trading/modeling** (planned): Track hypothetical positions and
  performance.

Current work is focused on **Milestone 4 – API & Backend**, especially the first
slice of stock and sentiment/price endpoints.

### Project layout

Relevant backend structure (simplified):

- `backend/app/main.py` – FastAPI application factory and router wiring.
- `backend/app/config.py` – Centralized configuration via Pydantic settings.
- `backend/app/models/` – ORM models (`Stock`, `RedditPost`, `PriceData`, …).
- `backend/app/data/` – Database setup and repository layer.
- `backend/app/services/` – Business logic (sentiment, patterns, activity, APIs).
- `backend/app/api/` – FastAPI route modules.
- `backend/tests/` – Pytest suite for config, services, repositories, and APIs.
- `PLAN.md` – Detailed project plan, milestones, and business logic.

### Prerequisites

- Python 3.11+ (recommended)
- SQLite (used via SQLAlchemy; no manual setup required for local dev)
- Git

### Installation

From the repository root:

```bash
cd /home/dgregor/projects/meme-stocks  # adjust if cloning elsewhere
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

### Configuration

Configuration is managed by `backend/app/config.py` using environment variables.
Defaults are safe for local development; secrets must be provided via the
environment or a `.env` file at the backend root.

Key settings (names in `.env` use upper‑case versions of these fields):

- `API_HOST` / `API_PORT` – Host and port for the FastAPI app.
- `LOG_LEVEL` – Logging level (e.g. `INFO`, `DEBUG`).
- `DATABASE_URL` – SQLAlchemy URL (default: a SQLite file under `data/`).
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` – Reddit API
  credentials for real data collection.
- Thresholds (with sensible defaults from `PLAN.md`):
  - `SENTIMENT_POSITIVE_THRESHOLD`
  - `SENTIMENT_NEGATIVE_THRESHOLD`
  - `VOLUME_SPIKE_THRESHOLD`
  - `PRICE_MOVEMENT_THRESHOLD`
  - `SENTIMENT_SHIFT_THRESHOLD`

Example minimal `.env` (for local development):

```bash
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///../data/app.db
REDDIT_CLIENT_ID=your-client-id
REDDIT_CLIENT_SECRET=your-client-secret
REDDIT_USER_AGENT=meme-stocks-app/0.1
```

### Running the backend

Activate your virtual environment and run the FastAPI app with Uvicorn:

```bash
cd /home/dgregor/projects/meme-stocks
source .venv/bin/activate
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

The server will expose:

- `GET /health` – Simple health check.
- `GET /api/stocks` – List known stocks.
- `GET /api/stocks/{symbol}` – Details for a single stock.
- `GET /api/stocks/{symbol}/sentiment` – Aggregated Reddit sentiment for a stock.
- `GET /api/stocks/{symbol}/prices` – Stored historical price data for a stock.

Interactive API docs will be available at `/docs` and `/redoc` once the app is
running.

### Running tests

The project uses **pytest** with a fairly comprehensive test suite under
`backend/tests/`.

```bash
cd /home/dgregor/projects/meme-stocks
source .venv/bin/activate
pytest
```

Tests include:

- Configuration and settings validation.
- Repository / database behavior.
- External service wrappers (Reddit, Yahoo).
- Analysis logic (sentiment, patterns, activity detection).
- API endpoints implemented so far.

### Development guidelines

- **Follow `PLAN.md`** for milestones and scope; avoid adding endpoints or
  features that are not described there without updating the plan.
- **No silent failures**: prefer explicit exceptions and clear error responses.
- **Keep business logic in services**, not API route handlers.
- **Always add or update tests** when changing backend logic (especially
  services, repositories, or API routes).

For more details on trading strategies, thresholds, and future milestones, see
`PLAN.md`.


