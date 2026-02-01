# Product Requirements Document (PRD)
## Meme Stocks Trading Application

**Version:** 1.0
**Last Updated:** January 31, 2026
**Status:** MVP Complete

---

## 1. Executive Summary

The Meme Stocks Trading Application is a web-based tool designed for retail investors who want to analyze meme stocks using a combination of social sentiment data and technical price patterns. The application aggregates Reddit discussions, calculates sentiment scores, monitors price movements, and provides actionable insights through end-of-day analysis and real-time notifications.

This is a decision-support tool for manual trading—it does not execute trades automatically or integrate with brokers.

---

## 2. Problem Statement

### Current Pain Points

1. **Information Overload**: Retail investors struggle to keep up with the rapid pace of social media discussions about meme stocks across multiple subreddits.

2. **Signal vs. Noise**: It's difficult to distinguish genuine sentiment shifts from random noise in social media chatter.

3. **Missed Opportunities**: Volume spikes, price movements, and sentiment shifts often happen quickly; without automated monitoring, investors miss critical entry/exit points.

4. **Manual Tracking Burden**: Tracking multiple stocks, their sentiment trends, and price patterns manually is time-consuming and error-prone.

5. **No Practice Environment**: New investors lack a safe way to test trading strategies without risking real money.

### How This Product Solves These Problems

- **Automated Data Collection**: Continuously monitors Reddit and Yahoo Finance, eliminating manual data gathering.
- **Sentiment Quantification**: Transforms qualitative social media discussions into actionable sentiment scores.
- **Unusual Activity Alerts**: Proactively notifies users of significant volume spikes, price movements, and sentiment shifts.
- **Consolidated Analysis**: Provides ranked daily summaries combining sentiment and technical analysis.
- **Paper Trading**: Enables risk-free strategy testing with full performance tracking.

---

## 3. Target Users

### Primary Persona: Retail Meme Stock Investor

**Demographics:**
- Age: 18-45
- Experience: Beginner to intermediate trader
- Time availability: Part-time (1-2 hours/day for research)
- Portfolio size: $1,000 - $50,000

**Characteristics:**
- Actively follows r/wallstreetbets, r/stocks, and similar subreddits
- Makes manual trading decisions through their existing brokerage
- Interested in both short-term momentum plays and swing trades
- Values data-driven insights but doesn't have time for deep technical analysis
- Wants to improve trading skills without risking capital initially

**Goals:**
- Identify high-potential meme stocks before they "moon"
- Avoid bagholding by detecting sentiment reversals early
- Track portfolio performance and learn from past trades
- Stay informed about unusual market activity throughout the day

### Secondary Persona: Hobbyist Quant

**Characteristics:**
- Has programming knowledge
- Wants to understand and potentially extend the analysis algorithms
- May use the data for their own research

---

## 4. Goals and Objectives

### Product Goals

| Goal | Success Metric | Target |
|------|----------------|--------|
| Reduce research time | Time spent on manual Reddit browsing | 50% reduction |
| Improve signal quality | False positive rate on alerts | < 30% |
| Enable practice trading | Users creating paper trades | 80% of active users |
| Provide timely alerts | Alert delivery latency | < 5 minutes from event |
| Daily engagement | Users checking daily analysis | 70% daily active rate |

### Business Objectives

1. **MVP Validation**: Confirm core value proposition with target users
2. **Feature Completeness**: Deliver all planned functionality through Milestone 7
3. **Reliability**: Achieve 99% uptime for background data collection
4. **Extensibility**: Architecture supports future enhancements (ML sentiment, additional data sources)

---

## 5. Features and Requirements

### 5.0 Reliability Principles

These principles apply to all code in this project. They ensure the application fails explicitly, degrades gracefully, and remains debuggable. **Coding agents and developers must follow these principles.**

1. **No Silent Failures**
   - Never swallow exceptions. Log errors and surface meaningful signals to callers.
   - For external APIs (Reddit, Yahoo), handle network failures, invalid responses, and rate limiting explicitly. Do not catch and ignore.

2. **Explicit Error Surfaces**
   - When an operation fails, return a clear error (e.g., `ExternalAPIError`, `NotFoundError`) with enough context for the caller to understand what went wrong.
   - API endpoints must return structured error responses (see Appendix C), not raw stack traces.

3. **Graceful Degradation**
   - If Reddit or Yahoo is unavailable, return an error or "no data" response—do not crash the application or return fabricated defaults.
   - Background jobs must not crash the app on external API failure; log the error and continue (e.g., run the next scheduled job).

4. **Actionable Error Messages**
   - Error messages must be specific: include what failed, why (when known), and any relevant context (e.g., symbol, job name, subreddit).
   - Example: "Failed to fetch Reddit posts for r/wallstreetbets: rate limited (retry after 60s)" instead of "Request failed."

5. **Data Integrity**
   - When data is missing or incomplete, return a clear "no data" signal. Do not fabricate or guess values.
   - Prefer returning `None`, `[]`, or an explicit "no data" response over silent defaults.

### 5.1 Functional Requirements

#### FR-1: Social Sentiment Analysis

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-1.1 | Collect posts from configurable subreddits (wallstreetbets, stocks, investing) | Must Have | ✅ Complete |
| FR-1.2 | Extract stock ticker symbols from post titles | Must Have | ✅ Complete |
| FR-1.3 | Calculate sentiment score (-1 to +1) using keyword-based analysis | Must Have | ✅ Complete |
| FR-1.4 | Weight sentiment by engagement (upvotes, comments) | Must Have | ✅ Complete |
| FR-1.5 | Apply time decay to older posts | Must Have | ✅ Complete |
| FR-1.6 | Aggregate sentiment per stock symbol | Must Have | ✅ Complete |
| FR-1.7 | Track sentiment trends over time (momentum) | Should Have | ✅ Complete |
| FR-1.8 | Support ML-based sentiment analysis | Could Have | ❌ Future |

#### FR-2: Price Pattern Analysis

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-2.1 | Fetch historical price data from Yahoo Finance | Must Have | ✅ Complete |
| FR-2.2 | Calculate Simple Moving Averages (20-day, 50-day) | Must Have | ✅ Complete |
| FR-2.3 | Classify price trends (uptrend, downtrend, sideways) | Must Have | ✅ Complete |
| FR-2.4 | Detect volume spikes relative to average | Must Have | ✅ Complete |
| FR-2.5 | Calculate RSI (Relative Strength Index) | Should Have | ❌ Future |
| FR-2.6 | Detect price breakouts and breakdowns | Should Have | ❌ Future |
| FR-2.7 | Identify support/resistance levels | Could Have | ❌ Future |

#### FR-3: Unusual Activity Detection & Notifications

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-3.1 | Detect volume spikes (> configurable threshold, default 2x average) | Must Have | ✅ Complete |
| FR-3.2 | Detect significant price movements (> configurable %, default 5%) | Must Have | ✅ Complete |
| FR-3.3 | Detect sentiment shifts (> configurable threshold, default 0.3) | Must Have | ✅ Complete |
| FR-3.4 | Create notifications with severity levels (low, medium, high) | Must Have | ✅ Complete |
| FR-3.5 | Store and retrieve notification history | Must Have | ✅ Complete |
| FR-3.6 | WebSocket real-time notification push | Could Have | ❌ Deferred |
| FR-3.7 | Combined multi-signal alerts | Could Have | ❌ Future |

#### FR-4: End-of-Day Analysis

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-4.1 | Generate daily ranked stock summary | Must Have | ✅ Complete |
| FR-4.2 | Calculate composite score (sentiment + price + volume) | Must Have | ✅ Complete |
| FR-4.3 | Categorize stocks (Top Opportunities, Watchlist, Avoid) | Should Have | ❌ Future |
| FR-4.4 | Compare to 7-day trends | Could Have | ❌ Future |

#### FR-5: Paper Trading

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-5.1 | Create paper trades (buy/sell with price and quantity) | Must Have | ✅ Complete |
| FR-5.2 | Track open positions with unrealized P/L | Must Have | ✅ Complete |
| FR-5.3 | Close positions and calculate realized P/L | Must Have | ✅ Complete |
| FR-5.4 | View portfolio summary (total value, P/L) | Must Have | ✅ Complete |
| FR-5.5 | Trade history with performance metrics | Must Have | ✅ Complete |
| FR-5.6 | Calculate win rate and average win/loss | Should Have | ❌ Future |

#### FR-6: Symbol Universe Management

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-6.1 | Maintain whitelist of valid stock symbols | Must Have | ✅ Complete |
| FR-6.2 | Fetch symbols from SEC EDGAR | Must Have | ✅ Complete |
| FR-6.3 | Filter ticker extraction to reduce false positives | Must Have | ✅ Complete |
| FR-6.4 | Auto-discover new stocks from Reddit mentions | Must Have | ✅ Complete |

#### FR-7: Background Jobs

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-7.1 | Scheduled Reddit data collection (configurable interval) | Must Have | ✅ Complete |
| FR-7.2 | Scheduled price data updates (configurable interval) | Must Have | ✅ Complete |
| FR-7.3 | Scheduled daily analysis generation | Must Have | ✅ Complete |
| FR-7.4 | Scheduled notification checks | Must Have | ✅ Complete |
| FR-7.5 | Catch-up logic for missed jobs on startup | Must Have | ✅ Complete |
| FR-7.6 | Job execution tracking in database | Must Have | ✅ Complete |

### 5.2 Non-Functional Requirements

#### NFR-1: Performance

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1.1 | API response time for list endpoints | < 500ms (p95) |
| NFR-1.2 | API response time for detail endpoints | < 200ms (p95) |
| NFR-1.3 | Background job completion time | < 60 seconds |
| NFR-1.4 | Frontend page load time | < 2 seconds |

#### NFR-2: Reliability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-2.1 | Application uptime | 99% (excluding planned maintenance) |
| NFR-2.2 | Data collection success rate | > 95% |
| NFR-2.3 | Graceful handling of external API failures | 100% (no crashes) |
| NFR-2.4 | Database integrity | No data corruption |

#### NFR-3: Scalability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-3.1 | Tracked stocks | Support up to 500 stocks |
| NFR-3.2 | Historical data retention | 1 year of price data per stock |
| NFR-3.3 | Reddit posts per day | Handle 10,000+ posts |
| NFR-3.4 | Concurrent users | Support 10 simultaneous users |

#### NFR-4: Security

| ID | Requirement | Status |
|----|-------------|--------|
| NFR-4.1 | No hardcoded secrets (use environment variables) | ✅ Implemented |
| NFR-4.2 | Input validation on all API endpoints | ✅ Implemented |
| NFR-4.3 | CORS configured for frontend origin only | ✅ Implemented |
| NFR-4.4 | No PII collection or storage | ✅ By design |

#### NFR-5: Maintainability

| ID | Requirement | Status |
|----|-------------|--------|
| NFR-5.1 | Modular architecture (services, repositories, routes) | ✅ Implemented |
| NFR-5.2 | Comprehensive test coverage (unit + integration) | ✅ Implemented |
| NFR-5.3 | Type hints throughout Python codebase | ✅ Implemented |
| NFR-5.4 | Pre-commit hooks (black, flake8, mypy) | ✅ Configured |

#### NFR-6: Usability

| ID | Requirement | Status |
|----|-------------|--------|
| NFR-6.1 | Responsive web design | ✅ Implemented |
| NFR-6.2 | Clear error messages in UI | ✅ Implemented |
| NFR-6.3 | Auto-refresh for dynamic data | ❌ Future |
| NFR-6.4 | Mobile-friendly layout | ❌ Future |

---

## 6. User Stories

### Epic 1: Sentiment Monitoring

**US-1.1** As a retail investor, I want to see the current sentiment score for a stock so that I can gauge market mood before trading.

**US-1.2** As a retail investor, I want to know how many times a stock was mentioned on Reddit today so that I can understand its popularity.

**US-1.3** As a retail investor, I want to see if sentiment is improving or declining so that I can anticipate momentum shifts.

### Epic 2: Price Analysis

**US-2.1** As a retail investor, I want to see historical price data for a stock so that I can understand its recent performance.

**US-2.2** As a retail investor, I want to know if a stock is in an uptrend or downtrend so that I can align my trades with the trend.

**US-2.3** As a retail investor, I want to be alerted when volume is unusually high so that I don't miss potential opportunities.

### Epic 3: Notifications

**US-3.1** As a retail investor, I want to receive alerts when a stock I follow has unusual activity so that I can react quickly.

**US-3.2** As a retail investor, I want to see all my unread notifications in one place so that I don't miss important updates.

**US-3.3** As a retail investor, I want configurable alert thresholds so that I can control the frequency of notifications.

### Epic 4: Daily Analysis

**US-4.1** As a retail investor, I want a daily summary of top-ranked stocks so that I know where to focus my attention.

**US-4.2** As a retail investor, I want to see a combined score based on sentiment and price patterns so that I have a single actionable metric.

### Epic 5: Paper Trading

**US-5.1** As a beginner investor, I want to practice trades without real money so that I can learn without risk.

**US-5.2** As a paper trader, I want to track my portfolio's performance over time so that I can evaluate my strategy.

**US-5.3** As a paper trader, I want to close positions and see my realized profit/loss so that I know how well I traded.

### Epic 6: Stock Management

**US-6.1** As a user, I want the app to automatically discover stocks mentioned on Reddit so that I don't have to manually add them.

**US-6.2** As a user, I want to see a list of all tracked stocks so that I can browse and select ones to analyze.

---

## 7. Technical Architecture

### 7.1 System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         User's Browser                          │
│                        (React Frontend)                         │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 │ HTTP/REST
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   API       │  │  Services   │  │    Background Jobs      │  │
│  │   Routes    │──│  (Business  │──│    (APScheduler)        │  │
│  │             │  │   Logic)    │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│         │                │                      │               │
│         └────────────────┼──────────────────────┘               │
│                          │                                      │
│                   ┌──────▼──────┐                               │
│                   │ Repositories│                               │
│                   │ (Data Layer)│                               │
│                   └──────┬──────┘                               │
└──────────────────────────┼──────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  SQLite  │ │  Reddit  │ │  Yahoo   │
        │ Database │ │   API    │ │ Finance  │
        └──────────┘ └──────────┘ └──────────┘
```

### 7.2 Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | React + TypeScript + Vite | User interface |
| Backend | FastAPI (Python 3.11+) | REST API server |
| Database | SQLite | Persistent data storage |
| Scheduling | APScheduler | Background job execution |
| Reddit API | PRAW | Social media data collection |
| Finance API | yfinance | Market data collection |
| Testing | pytest | Backend test suite |

### 7.3 Data Models

| Model | Description | Key Fields |
|-------|-------------|------------|
| Stock | Tracked stock symbols | symbol (PK), name, sector, market_cap |
| SymbolUniverse | Valid stock symbols whitelist | symbol (PK), exchange, is_active |
| RedditPost | Reddit submissions | id (PK), subreddit, title, author, upvotes, comments, url, posted_at, collected_at |
| RedditSymbolMention | Links posts to symbols | post_id + symbol (composite PK) |
| PriceData | Historical OHLCV data | stock_symbol, date, open, high, low, close, volume |
| Notification | Activity alerts | stock_symbol, type, severity, message, read |
| PaperTrade | Simulated trades | stock_symbol, action, quantity, entry_price, exit_price |
| JobExecution | Background job tracking | job_name, last_run_at |

---

## 8. Configuration

All thresholds and settings are configurable via environment variables:

### Analysis Thresholds

| Variable | Default | Description |
|----------|---------|-------------|
| SENTIMENT_POSITIVE_THRESHOLD | 0.3 | Score above which sentiment is considered positive |
| SENTIMENT_NEGATIVE_THRESHOLD | -0.2 | Score below which sentiment is considered negative |
| VOLUME_SPIKE_THRESHOLD | 2.0 | Multiplier for volume spike detection |
| PRICE_MOVEMENT_THRESHOLD_PCT | 5.0 | Percentage move for price alerts |
| SENTIMENT_SHIFT_THRESHOLD | 0.3 | Change threshold for sentiment shift alerts |

### Scheduling

| Variable | Default | Description |
|----------|---------|-------------|
| REDDIT_COLLECTION_INTERVAL_MINUTES | 60 | How often to fetch Reddit data |
| PRICE_COLLECTION_INTERVAL_MINUTES | 15 | How often to update prices |
| NOTIFICATION_CHECK_INTERVAL_MINUTES | 30 | How often to scan for alerts |
| DAILY_ANALYSIS_HOUR | 16 | Hour (24h format) for daily analysis |
| REDDIT_SUBREDDITS | wallstreetbets,stocks,investing | Subreddits to monitor |
| ENABLE_CATCH_UP | true | Run missed jobs on startup |

---

## 9. Assumptions and Constraints

### Assumptions

1. **Users have basic trading knowledge**: The app does not teach trading fundamentals.
2. **Users have their own brokerage**: No broker integration; all trades are manual.
3. **Reddit is a valid signal source**: Social sentiment on Reddit correlates with meme stock movements.
4. **Free APIs are sufficient**: Reddit and Yahoo Finance free tiers meet our data needs.
5. **Single-user deployment**: Initial version is for personal use, not multi-tenant.

### Constraints

1. **No real money at risk**: Paper trading only; no live trading integration.
2. **API rate limits**: Reddit and Yahoo Finance impose rate limits on free usage.
3. **SQLite limitations**: Single-writer constraint; not suitable for high concurrency.
4. **Sentiment accuracy**: Keyword-based sentiment is approximate, not production ML quality.
5. **Market hours only**: Price data is only meaningful during market hours.

---

## 10. Out of Scope (Future Considerations)

The following features are explicitly not included in the current scope but may be considered for future versions:

1. **ML-based sentiment analysis**: Replace keyword matching with trained NLP models
2. **Real-time WebSocket notifications**: Push notifications to the browser
3. **Advanced technical indicators**: RSI, MACD, Bollinger Bands, etc.
4. **Multi-user authentication**: User accounts with personalized watchlists
5. **Broker integration**: Connect to Robinhood, TD Ameritrade, etc. for live trading
6. **Mobile app**: Native iOS/Android applications
7. **Options data**: Track options flow and unusual options activity
8. **News integration**: Aggregate news headlines alongside social sentiment
9. **Backtesting engine**: Test strategies against historical data
10. **Discord/Telegram alerts**: Push notifications to messaging platforms

---

## 11. Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Reddit API rate limiting | Medium | High | Implement caching, respect rate limits, use exponential backoff |
| Yahoo Finance data gaps | Medium | Medium | Handle missing data gracefully, show "no data" state |
| Sentiment analysis inaccuracy | High | Medium | Expose as "directional indicator," not precise prediction |
| SQLite performance limits | Low | Medium | Design for PostgreSQL migration if needed |
| False positive ticker extraction | Medium | Low | Use symbol universe whitelist, maintain blacklist |
| External API changes | Low | High | Isolate API clients, monitor for breaking changes |

---

## 12. Success Metrics and KPIs

### Quantitative Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Data freshness | < 15 min for prices, < 60 min for Reddit | Check latest timestamps in DB |
| Alert precision | > 70% useful alerts | User feedback / manual review |
| Paper trading adoption | 80% of users create trades | Count users with trades |
| Daily analysis usage | 70% daily check rate | Page view analytics |
| Background job success | > 95% success rate | Job execution logs |

### Qualitative Goals

- Users report reduced time spent on manual research
- Users find the daily analysis actionable
- Paper trading helps users build confidence before real trading

---

## 13. Milestones (Completed)

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0 | Foundations & Test Framework | ✅ Complete |
| M1 | Data Layer & Models | ✅ Complete |
| M2 | Data Ingestion (Reddit, Yahoo) | ✅ Complete |
| M3 | Analysis Engine (Sentiment, Patterns, Activity) | ✅ Complete |
| M4 | API & Backend | ✅ Complete |
| M5 | Frontend MVP | ✅ Complete |
| M6 | Background Jobs & Refinement | ✅ Complete |
| M7 | Symbol Universe & Database Normalization | ✅ Complete |

---

## 14. Appendix

### A. API Endpoints Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check |
| GET | /api/stocks | List tracked stocks |
| GET | /api/stocks/{symbol} | Get stock details |
| GET | /api/stocks/{symbol}/sentiment | Get sentiment analysis |
| GET | /api/stocks/{symbol}/prices | Get price history |
| GET | /api/analysis/daily | Get daily ranked analysis |
| GET | /api/notifications | List unread notifications |
| POST | /api/trades | Create paper trade |
| GET | /api/trades | List paper trades |
| POST | /api/trades/{id}/close | Close paper trade |
| GET | /api/portfolio | Get portfolio summary |
| POST | /api/symbol-universe/refresh | Refresh symbol whitelist |
| GET | /api/symbol-universe/stats | Get symbol universe stats |

### B. Related Documents

- **PLAN.md**: Detailed project plan, architecture, and business logic
- **README.md**: Quick start guide and development instructions
- **.cursorrules**: Development guidelines and coding standards (references PRD §5.0)
- **.cursor/rules/reliability.mdc**: Always-applied rule for AI agents implementing Reliability Principles
- **.cursor/rules/agent-conduct.mdc**: Always-applied rule—be skeptical, don't oversell, verify before claiming

### C. API Error Response Format

All API endpoints must return structured errors (never raw stack traces). Use this format:

```json
{
  "error": true,
  "error_type": "DataFetchError",
  "message": "Human-readable description of what failed",
  "details": { "context": "optional additional context" }
}
```

Error types: `ExternalAPIError`, `DataAccessError` (see `backend/app/utils/errors.py`). Add `ValidationError`, `NotFoundError` as needed.

---

*This PRD is a living document and should be updated as the product evolves.*
