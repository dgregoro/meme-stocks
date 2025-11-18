# Meme Stocks Trading Application

A web application for analyzing meme stocks using social sentiment (Reddit) and price patterns. The app supports manual trading decisions with end-of-day analysis and real-time notifications for unusual activity. Includes paper trading/modeling capabilities.

## Status

**All planned milestones (0-6) are complete!** The application is fully functional with:
- ✅ Data collection from Reddit and Yahoo Finance
- ✅ Sentiment and price pattern analysis
- ✅ RESTful API with all endpoints
- ✅ React frontend (MVP)
- ✅ Background jobs with catch-up functionality
- ✅ Paper trading system

## Features

### Implemented

- **Social Sentiment Analysis**: Reddit data collection with keyword-based sentiment scoring, engagement weighting, and time decay
- **Price Pattern Analysis**: Historical price data from Yahoo Finance with technical indicators (SMA-based trend detection)
- **Unusual Activity Detection**: Volume spikes, price movements, and sentiment shift alerts
- **End-of-Day Analysis**: Daily ranked stock summaries with composite scoring
- **Paper Trading**: Track hypothetical positions, portfolio performance, and trade history
- **Background Jobs**: Automated data collection with catch-up on startup (handles laptop sleep/wake gracefully)
- **Ticker Extraction**: Automatic stock symbol detection from Reddit post titles
- **Notifications**: Real-time alerts for unusual activity (volume spikes, price moves, sentiment shifts)

### API Endpoints

- `GET /health` - Health check
- `GET /api/stocks` - List all tracked stocks
- `GET /api/stocks/{symbol}` - Get stock details
- `GET /api/stocks/{symbol}/sentiment` - Get sentiment analysis for a stock
- `GET /api/stocks/{symbol}/prices` - Get historical price data
- `GET /api/analysis/daily` - Get ranked daily analysis summary
- `GET /api/notifications` - List unread notifications
- `POST /api/trades` - Create a paper trade
- `GET /api/trades` - List all paper trades
- `POST /api/trades/{id}/close` - Close a paper trade
- `GET /api/portfolio` - Get portfolio summary

Interactive API docs available at `/docs` and `/redoc` when the server is running.

## Quick Start

### Backend

1. **Install dependencies**:

```bash
cd backend
pip install -r requirements.txt
```

2. **Configure environment** (optional, defaults work for local dev):

Create `backend/.env`:
```bash
LOG_LEVEL=INFO
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

3. **Run tests**:

```bash
cd ..
python -m pytest backend/tests/ -v
```

4. **Start the API**:

```bash
uvicorn backend.app.main:app --reload
```

The server will start at `http://127.0.0.1:8000`. Visit `/health` to confirm it's running.

### Frontend

1. **Install dependencies**:

```bash
cd frontend
npm install
```

2. **Configure API base** (optional, defaults to `http://127.0.0.1:8000`):

Create `frontend/.env`:
```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

3. **Run dev server**:

```bash
npm run dev
```

Open the printed URL (default `http://127.0.0.1:5173`).

## Background Jobs

The application includes automated background jobs that run on a schedule:

- **Reddit Collection**: Fetches recent posts from configured subreddits (default: hourly)
- **Price Collection**: Updates price data for tracked stocks (default: every 15 minutes)
- **Daily Analysis**: Generates end-of-day analysis (default: 4 PM)
- **Notification Checks**: Scans for unusual activity (default: every 30 minutes)

**Catch-up Functionality**: When the app starts (e.g., after laptop was off), it automatically checks for missed jobs and runs them. This ensures you don't miss data even if the laptop was sleeping.

All job intervals and subreddits are configurable via environment variables (see Configuration section above).

## Project Structure

```
meme-stocks/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── config.py            # Configuration management
│   │   ├── models/               # SQLAlchemy ORM models
│   │   ├── api/                 # FastAPI route modules
│   │   ├── services/             # Business logic (sentiment, patterns, scheduler)
│   │   ├── data/                # Database setup and repositories
│   │   └── utils/               # Utilities (ticker extraction, errors)
│   ├── tests/                   # Pytest test suite
│   └── requirements.txt         # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── pages/               # React pages (Dashboard, Stocks, etc.)
│   │   ├── services/            # API client
│   │   └── App.tsx              # Main app component
│   └── package.json
├── PLAN.md                      # Detailed project plan and milestones
└── README.md                    # This file
```

## Configuration

Configuration is managed via environment variables (see `backend/app/config.py`). Key settings:

### Core Settings
- `API_HOST`, `API_PORT` - Server host/port (default: `127.0.0.1:8000`)
- `LOG_LEVEL` - Logging level (default: `INFO`)
- `DATABASE_URL` - SQLAlchemy database URL (default: `sqlite:///./data/app.db`)

### Reddit API
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` - Reddit API credentials (required for data collection)
- `REDDIT_USER_AGENT` - User agent string (default: `meme-stocks-app/0.1`)

### Analysis Thresholds
- `SENTIMENT_POSITIVE_THRESHOLD` (default: `0.3`)
- `SENTIMENT_NEGATIVE_THRESHOLD` (default: `-0.2`)
- `VOLUME_SPIKE_THRESHOLD` (default: `2.0`)
- `PRICE_MOVEMENT_THRESHOLD_PCT` (default: `5.0`)
- `SENTIMENT_SHIFT_THRESHOLD` (default: `0.3`)

### Scheduling
- `REDDIT_COLLECTION_INTERVAL_MINUTES` (default: `60`)
- `PRICE_COLLECTION_INTERVAL_MINUTES` (default: `15`)
- `NOTIFICATION_CHECK_INTERVAL_MINUTES` (default: `30`)
- `DAILY_ANALYSIS_HOUR` (default: `16` - 4 PM)
- `REDDIT_SUBREDDITS` (default: `wallstreetbets,stocks,investing`)
- `ENABLE_CATCH_UP` (default: `true`)

### CORS
- `CORS_ALLOWED_ORIGINS` (default: `http://127.0.0.1:5173,http://localhost:5173`)

## Development

### Prerequisites

- Python 3.11+ (recommended)
- Node.js 18+ (for frontend)
- SQLite (used via SQLAlchemy; no manual setup required)

### Running Tests

```bash
# All tests
python -m pytest backend/tests/ -v

# Specific test file
python -m pytest backend/tests/test_scheduler_service.py -v
```

The test suite includes:
- Configuration and settings validation
- Repository / database behavior
- External service wrappers (Reddit, Yahoo Finance)
- Analysis logic (sentiment, patterns, activity detection)
- API endpoints
- Background scheduler and catch-up logic

### Pre-commit Hooks

This repository includes `.pre-commit-config.yaml` with:
- **Core checks**: large-file detection, merge-conflict markers, whitespace fixes
- **Formatting**: `black` (Python code formatter)
- **Linting**: `flake8`
- **Type checking**: `mypy`

To enable:

```bash
pip install pre-commit
pre-commit install
```

Run manually:

```bash
pre-commit run --all-files
```

### Development Guidelines

- **Follow `PLAN.md`**: Milestones and scope are documented there
- **No silent failures**: Prefer explicit exceptions and clear error responses
- **Keep business logic in services**: Not in API route handlers
- **Always add/update tests**: When changing backend logic (services, repositories, API routes)
- **Timezone-aware datetimes**: Use `datetime.now(timezone.utc)`, not `datetime.utcnow()`

## Tech Stack

### Backend
- **FastAPI** - Modern async web framework
- **SQLAlchemy** - ORM and database toolkit
- **PRAW** - Python Reddit API Wrapper
- **yfinance** - Yahoo Finance data library
- **APScheduler** - Background job scheduling
- **pytest** - Testing framework

### Frontend
- **React** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server

## Documentation

- **`PLAN.md`** - Detailed project plan, milestones, business logic, and trading strategies
- **API Docs** - Available at `/docs` when the server is running
- **Code comments** - Inline documentation throughout the codebase

## License

[Add your license here]

## Contributing

[Add contribution guidelines if applicable]
