# Meme Stocks Trading Application

A web application for analyzing meme stocks using **price patterns**, technical signals, scheduled jobs, and optional research workflows. It supports manual trading decisions with end-of-day analysis, notifications for unusual activity, and paper trading.

**Historical note:** The project **originally** focused on **Reddit** as the main social signal (ingest posts, ticker extraction, keyword sentiment, and lead–lag research against prices). **Reddit ingestion has been removed** from the codebase. Day-to-day behavior is **price-centric** (Yahoo Finance and related pipelines); some APIs and datasets still expose legacy “mention” columns as zeros for compatibility. For the full product-doc treatment, see **[docs/PRD.md](docs/PRD.md)** (scope callout at the top).

**North star:** Personal, data-driven trading research: **hypothesis → measurable edge (or kill) → disciplined execution**; AI for engineering and selective modeling, not instead of validation. Full wording: **[docs/PURPOSE.md](docs/PURPOSE.md)**.

## Research Track: Lead–lag / predictiveness (historically Reddit-oriented)

The repo still supports **causal-style analysis** and research datasets (e.g., **[docs/CAUSAL_RESEARCH.md](docs/CAUSAL_RESEARCH.md)**). That line of work **used to** center on Reddit mentions vs returns; **without a live social feed**, mention series in tooling are often empty or placeholder, while **price and label** paths remain active. Principles still apply:

- **Time alignment** and **no look-ahead** when building datasets.
- Prefer interpretable baselines before heavy ML.

See: **[docs/CAUSAL_RESEARCH.md](docs/CAUSAL_RESEARCH.md)**.

## Status

**All planned milestones (M0-M7) are complete!** The application is fully functional with:
- ✅ Price data collection (Yahoo Finance) and scheduled jobs
- ✅ Pattern / trend analysis and ranked daily summary (sentiment fields are legacy; no live social feed)
- ✅ RESTful API and React frontend (MVP)
- ✅ Background jobs with catch-up functionality
- ✅ Paper trading system
- ✅ Symbol universe for ticker validation

## Features

### Implemented

- **Price & pattern analysis**: Historical prices from Yahoo Finance; SMA-style trends, RSI, volume-aware signals where implemented
- **Keyword sentiment helpers**: Still used in ranking **when applied to empty or future non-Reddit text**; dashboard “mentions” stay at zero without a feed
- **Unusual Activity Detection**: Volume spikes, price movements, optional sentiment-shift scoring in combined alerts
- **End-of-Day Analysis**: Daily ranked stock summaries with composite scoring
- **Paper Trading**: Track hypothetical stock and option positions, portfolio performance, and trade history
- **Background Jobs**: Price collection, notifications, daily analysis slot, intraday/leader-follower when enabled
- **Ticker extraction utilities**: Originally tuned for social text; still usable for watchlists / universe workflows
- **Notifications**: Alerts for unusual activity (volume, price moves, combined scoring)

### API Endpoints

- `GET /health` - Health check
- `GET /api/stocks` - List all tracked stocks
- `GET /api/stocks/{symbol}` - Get stock details
- `GET /api/stocks/{symbol}/prices` - Get historical price data
- `GET /api/analysis/daily` - Get ranked daily analysis summary (includes sentiment_score / mention_count fields for API stability)
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
