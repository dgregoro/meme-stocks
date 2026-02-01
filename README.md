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

## Getting Started

See **[GETTING_STARTED.md](GETTING_STARTED.md)** for setup, configuration, and development instructions.

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
├── GETTING_STARTED.md            # Setup and development guide
├── PLAN.md                      # Detailed project plan and milestones
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

- **`GETTING_STARTED.md`** - Setup, configuration, and development instructions
- **`PLAN.md`** - Detailed project plan, milestones, business logic, and trading strategies
- **API Docs** - Available at `/docs` when the server is running
- **Code comments** - Inline documentation throughout the codebase

## License

[Add your license here]

## Contributing

[Add contribution guidelines if applicable]
