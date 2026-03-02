# Meme Stocks Trading Application

A web application for analyzing meme stocks using social sentiment (Reddit) and price patterns. The app supports manual trading decisions with end-of-day analysis and real-time notifications for unusual activity. Includes paper trading/modeling capabilities.

## Research Track: Reddit Mentions → Future Price Movement (Causation/Predictiveness)

In addition to the existing decision-support features, this repo is tracking a research direction:

> Evaluate whether changes in Reddit stock mentions *precede* and help *predict* (and potentially causally influence)
> future stock price movements.

Key constraints for this work:

- **Time alignment matters** (market hours vs after-hours posting).
- **Avoid look-ahead bias / leakage** when building training datasets.
- Start with simple, testable baselines (e.g., event studies / Granger-style tests) before more complex ML.

See: **[docs/CAUSAL_RESEARCH.md](docs/CAUSAL_RESEARCH.md)**.

## Status

**All planned milestones (M0-M7) are complete!** The application is fully functional with:
- ✅ Data collection from Reddit and Yahoo Finance
- ✅ Sentiment and price pattern analysis
- ✅ RESTful API with all endpoints
- ✅ React frontend (MVP)
- ✅ Background jobs with catch-up functionality
- ✅ Paper trading system
- ✅ Symbol universe for ticker validation

## Features

### Implemented

- **Social Sentiment Analysis**: Reddit data collection with keyword-based sentiment scoring, engagement weighting, and time decay
- **Price Pattern Analysis**: Historical price data from Yahoo Finance with technical indicators (SMA-based trend detection)
- **Unusual Activity Detection**: Volume spikes, price movements, and sentiment shift alerts
- **End-of-Day Analysis**: Daily ranked stock summaries with composite scoring
- **Paper Trading**: Track hypothetical stock and option positions, portfolio performance, and trade history
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
- `POST /api/trades` - Create a paper trade (stock or option)
- `GET /api/trades` - List all paper trades
- `POST /api/trades/{id}/close` - Close a paper trade
- `GET /api/portfolio` - Get portfolio summary

Interactive API docs available at `/docs` and `/redoc` when the server is running.

### CLI

Full API parity from the terminal. Requires a running backend.

```bash
# Run CLI (from project root)
python -m backend.cli.main health
python -m backend.cli.main stocks list
python -m backend.cli.main analysis --output json
python -m backend.cli.main portfolio
python -m backend.cli.main trades create GME buy 10 25.50
```

Use `python -m backend.cli.main --help` for all commands. Set `MEME_STOCKS_API_URL` or `--base-url` to point at your backend.

## Getting Started

- **[GETTING_STARTED.md](docs/GETTING_STARTED.md)** — Setup, configuration, and development instructions.
- **[USAGE.md](docs/USAGE.md)** — How to use the app (web UI and CLI).

**Quick run with containers** (portable, local editing supported):

```bash
podman-compose up --build
# App at http://localhost:8000
```

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
├── docs/                        # Documentation
│   ├── GETTING_STARTED.md       # Setup and development guide
│   ├── ARCHITECTURE.md          # Implementation patterns
│   ├── PRD.md                   # Product requirements
│   ├── ROADMAP.md               # Development roadmap
│   └── ...                      # Other docs
└── README.md                    # This file
```

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

- **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)** - Setup, configuration, and development instructions
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Implementation patterns for new features
- **[docs/PRD.md](docs/PRD.md)** - Product requirements and feature status
- **[docs/ROADMAP.md](docs/ROADMAP.md)** - Development roadmap and future work
- **[docs/PLAN.md](docs/PLAN.md)** - Business logic and trading algorithms
- **API Docs** - Available at `/docs` when the server is running
- **Code comments** - Inline documentation throughout the codebase

## License

[Add your license here]

## Contributing

[Add contribution guidelines if applicable]
