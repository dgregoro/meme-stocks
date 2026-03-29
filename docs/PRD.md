# Product Requirements Document (PRD)
## Meme Stocks Trading Application

**Version:** 1.0
**Last Updated:** February 28, 2026
**Status:** MVP Complete

---

## 1. Executive Summary

The Meme Stocks Trading Application is a web-based tool designed for retail investors who want to analyze meme stocks using a combination of social sentiment data and technical price patterns. The application aggregates Reddit discussions, calculates sentiment scores, monitors price movements, and provides actionable insights through end-of-day analysis and real-time notifications.

This is a decision-support tool for manual trading—it does not execute trades automatically or integrate with brokers. It is intended as a single-user application for personal use (for now). A command-line interface (CLI) provides full parity with the web UI for terminal users and scripting.

**Operator north star** (strategic intent, not a requirement to ship): personal, data-driven research—hypothesis → measurable edge (or kill) → disciplined execution; AI for engineering and selective modeling, not instead of validation. See **`docs/PURPOSE.md`**.

### 1.1 Spec-driven development

Before making functional changes to the application, update the spec to clarify the desired behavior. Then implement and test against the spec.

1. **Decide the behavior** — What should the system do? (e.g. "Per-symbol fetch failures are logged and do not stop the job.")
2. **Update the spec** — In this PRD: add or edit the relevant requirement in Section 5 (Features and Requirements), and if needed the API in Appendix A or user stories in Section 6. Update ROADMAP.md if the work is scheduled in a phase.
3. **Implement** — Code and tests should satisfy the updated PRD; follow ARCHITECTURE.md for structure.

### 1.2 Research Direction (Future Scope): Reddit Mentions → Price Movement

In addition to the MVP, this repo tracks a research direction:

- Evaluate whether Reddit mention activity *precedes* and helps *predict* future stock price movement.
- Avoid naive correlation by enforcing **time alignment** and preventing **look-ahead bias**.
- Prefer interpretable, testable methods first (event-study style analyses, Granger-style predictiveness tests),
  then iterate toward ML models once dataset construction is reliable and reproducible.

**Lead-lag evidence endpoint**: The `/api/analysis/causal/{symbol}` endpoint returns cross-correlation,
predictive regression, and placebo test results. It is explicitly labeled as **lead-lag evidence**, not
proven causality. Results should be interpreted with appropriate caution.

This research direction is documented in: `docs/CAUSAL_RESEARCH.md`

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
   - **Per-symbol failures**: When fetching data for a single symbol fails (e.g. price fetch for an invalid or unsupported ticker), log the symbol and the failure reason, then continue with the remaining symbols and jobs. The failure of one symbol must not stop the job or the application.

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
| FR-1.8 | Capture source of Reddit mentions (subreddit, post URL) and expose in web and CLI UIs | Must Have | ✅ Complete |
| FR-1.9 | Support ML-based sentiment analysis | Could Have | ❌ Future |

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
| FR-5.6 | Calculate win rate and average win/loss | Should Have | ✅ Complete |
| FR-5.7 | Support equity options (calls, puts with strike/expiry) | Should Have | ✅ Complete |

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
| FR-7.7 | Per-symbol fetch failures (e.g. invalid ticker, Yahoo/Reddit error) are logged with symbol and reason; job and application continue | Must Have | ✅ Complete |

#### FR-8: Command-Line Interface (CLI)

A fully functional CLI that provides parity with the web UI and API. The CLI operates as an API client: it requires a running backend and makes HTTP requests to the REST API. This ensures a single source of truth and avoids duplicating business logic.

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-8.1 | Connect to backend via configurable base URL (default http://127.0.0.1:8000) | Must Have | ❌ Future |
| FR-8.2 | Health check command (`meme-stocks health`) | Must Have | ❌ Future |
| FR-8.3 | Stock commands: list, show, create | Must Have | ❌ Future |
| FR-8.4 | Sentiment and price commands for a symbol | Must Have | ❌ Future |
| FR-8.5 | Daily analysis command (ranked summary) | Must Have | ❌ Future |
| FR-8.6 | Notifications command (list unread) | Must Have | ❌ Future |
| FR-8.7 | Paper trading: create trade, list trades, close trade, portfolio | Must Have | ❌ Future |
| FR-8.8 | Symbol universe: refresh, stats | Must Have | ❌ Future |
| FR-8.9 | Job commands: trigger reddit/price/notification collection, list job runs, recent Reddit posts | Must Have | ❌ Future |
| FR-8.10 | Human-readable table output for list endpoints (with optional JSON) | Must Have | ❌ Future |
| FR-8.11 | Structured error handling (API errors displayed clearly) | Must Have | ❌ Future |
| FR-8.12 | Global flags: `--base-url`, `--output json|table` | Should Have | ❌ Future |
| FR-8.13 | Shell completion (bash, zsh) | Could Have | ❌ Future |

**CLI Command Structure**

The CLI is invoked as `meme-stocks` (or `python -m backend.cli`) with subcommands. All commands require a running backend unless otherwise noted.

| Command | Description | API Equivalent |
|---------|-------------|----------------|
| `meme-stocks health` | Check backend connectivity | `GET /health` |
| `meme-stocks stocks list` | List all tracked stocks | `GET /api/stocks` |
| `meme-stocks stocks show SYMBOL` | Show stock details | `GET /api/stocks/{symbol}` |
| `meme-stocks stocks add SYMBOL [--name NAME]` | Add a stock to tracking | `POST /api/stocks` |
| `meme-stocks sentiment SYMBOL` | Show sentiment analysis | `GET /api/stocks/{symbol}/sentiment` |
| `meme-stocks stocks mentions SYMBOL` | Recent Reddit mentions for symbol (with source) | `GET /api/stocks/{symbol}/mentions` |
| `meme-stocks prices SYMBOL` | Show price history | `GET /api/stocks/{symbol}/prices` |
| `meme-stocks analysis` | Daily ranked analysis | `GET /api/analysis/daily` |
| `meme-stocks notifications` | List unread notifications | `GET /api/notifications` |
| `meme-stocks trades list` | List paper trades | `GET /api/trades` |
| `meme-stocks trades create SYMBOL buy|sell QTY PRICE [--option call\|put --strike N --expiry YYYY-MM-DD]` | Create paper trade | `POST /api/trades` |
| `meme-stocks trades close ID EXIT_PRICE` | Close a trade | `POST /api/trades/{id}/close` |
| `meme-stocks portfolio` | Portfolio summary | `GET /api/portfolio` |
| `meme-stocks symbols refresh` | Refresh symbol universe | `POST /api/symbol-universe/refresh` |
| `meme-stocks symbols stats` | Symbol universe stats | `GET /api/symbol-universe/stats` |
| `meme-stocks jobs reddit` | Trigger Reddit collection | `POST /api/jobs/reddit-collection` |
| `meme-stocks jobs prices` | Trigger price collection | `POST /api/jobs/price-collection` |
| `meme-stocks jobs notifications` | Trigger notification check | `POST /api/jobs/notification-check` |
| `meme-stocks jobs runs [JOB_NAME]` | List job execution history | `GET /api/jobs/{job_name}/runs` |
| `meme-stocks jobs recent-posts [--limit N]` | Recent Reddit posts | `GET /api/jobs/reddit-collection/recent` |

**Output Formats**

- **Table** (default): Human-readable tables for list endpoints (stocks, trades, analysis, notifications, etc.). Column widths adapt to terminal.
- **JSON** (`--output json`): Raw JSON for scripting and piping to `jq`.

**Configuration**

- `MEME_STOCKS_API_URL` or `--base-url`: Backend base URL (default `http://127.0.0.1:8000`).
- `MEME_STOCKS_OUTPUT`: Default output format (`table` or `json`).

**Error Handling**

- Connection refused / timeout: Clear message with suggested fix (e.g., "Backend not reachable. Is the server running? Try: uvicorn backend.app.main:app")
- API errors (4xx, 5xx): Display `error_type` and `message` from API response.
- Exit codes: 0 = success, 1 = client/validation error, 2 = server error, 3 = connection error.

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
| NFR-3.4 | Deployment model | Single-user; no multi-user or concurrency requirements |

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

#### NFR-7: CLI Usability (FR-8)

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-7.1 | CLI startup time | < 200ms |
| NFR-7.2 | Help text for all commands | Every command has `--help` |
| NFR-7.3 | Table output fits 80-column terminals | Columns truncate or wrap gracefully |
| NFR-7.4 | Scriptable (non-interactive) | All commands work without TTY |

### 5.3 Web UI Enhancement Ideas

The following are candidate improvements to the web UI. They are not yet committed requirements; prioritize via ROADMAP.md and user feedback.

#### Visual design & branding

| Idea | Description | Priority (suggested) |
|------|-------------|----------------------|
| Theming | Light/dark mode toggle with persistence (e.g. localStorage). | High |
| Typography & spacing | Distinct font stack, consistent spacing scale, and clear hierarchy so screens are scannable. | High |
| Color semantics | Use color consistently (e.g. green/red for positive/negative sentiment and P/L, severity for notifications). | High |
| Branding | App name, favicon, and optional header/footer to reinforce product identity. | Medium |

#### Navigation & layout

| Idea | Description | Priority (suggested) |
|------|-------------|----------------------|
| Persistent navigation | Sidebar or top nav with clear sections (Dashboard, Stocks, Notifications, Paper Trading) and active state. | High |
| Stock-centric flow | From Dashboard or Stocks list, drill into a stock detail view (sentiment, mentions, price, trend) without losing context. | High |
| Breadcrumbs or back | When drilling into a stock or trade, easy way to return to list or dashboard. | Medium |
| Landing / empty states | First-time or empty state (no stocks, no notifications) with short guidance or call-to-action. | Medium |

#### Data presentation

| Idea | Description | Priority (suggested) |
|------|-------------|----------------------|
| Dashboard summary cards | At-a-glance counts or highlights (e.g. unread notifications, top mover, last job run) on Dashboard. | High |
| Sortable/filterable tables | Sort columns on Dashboard (composite, sentiment, mentions) and filter stocks or notifications. | High |
| Price charts | Sparklines or a small price chart (e.g. last 7–30 days) per symbol on Dashboard or stock detail. | High |
| Sentiment visualization | Simple gauge, bar, or badge for sentiment score and classification (positive/neutral/negative). | Medium |
| Relative time | Show “2 hours ago” for notifications and job runs where helpful; keep exact time on hover or detail. | Medium |
| Reddit mentions list | Structured list of mentions (subreddit, title, link, upvotes) with optional expand/collapse. | Medium |

#### Interactivity & feedback

| Idea | Description | Priority (suggested) |
|------|-------------|----------------------|
| Auto-refresh | Optional periodic refresh for Dashboard or notifications (e.g. every N minutes) with indicator. | High (NFR-6.3) |
| Loading states | Skeleton or spinner for list/detail loads so the UI doesn’t feel stuck. | High |
| Toasts or inline success/error | Confirm actions (e.g. trade created, stock added) and surface API errors clearly. | High |
| Confirm destructive actions | Confirm before closing a trade or removing data. | Medium |
| Mark notification read | Per-notification or “mark all read” with immediate UI update. | Medium |

#### Responsiveness & accessibility

| Idea | Description | Priority (suggested) |
|------|-------------|----------------------|
| Mobile-friendly tables | On small screens, cards or stacked layout instead of wide tables; primary actions visible. | High |
| Keyboard & focus | Logical tab order, focus indicators, and key shortcuts (e.g. Escape to close modals). | Medium |
| Screen reader support | Semantic HTML, ARIA where needed, and labels so core flows work with assistive tech. | Medium |

#### Performance & polish

| Idea | Description | Priority (suggested) |
|------|-------------|----------------------|
| Per-route code splitting | Lazy-load Dashboard, Stocks, Paper Trading so initial load stays fast. | Medium |
| Optimistic updates | For create/close trade, update UI immediately and reconcile on server response. | Low |
| Last-updated indicator | Show when data was last refreshed (e.g. “Prices as of 14:32 UTC”) to set expectations. | Low |

---

## 6. User Stories

### Epic 1: Sentiment Monitoring

**US-1.1** As a retail investor, I want to see the current sentiment score for a stock so that I can gauge market mood before trading.

**US-1.2** As a retail investor, I want to know how many times a stock was mentioned on Reddit today so that I can understand its popularity.

**US-1.2a** As a retail investor, I want to see the source of each Reddit mention (subreddit and link to the post) so that I can verify and dive into the discussion.

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

### Epic 7: Command-Line Interface

**US-7.1** As a terminal user, I want to run all app operations from the command line so that I can work without a browser.

**US-7.2** As a power user, I want JSON output for list commands so that I can script workflows and pipe to `jq` or other tools.

**US-7.3** As a developer, I want to trigger background jobs manually via CLI so that I can test data collection without waiting for the scheduler.

**US-7.4** As a paper trader, I want to create and close trades from the terminal so that I can integrate paper trading into my existing workflow.

**US-7.5** As a user, I want clear error messages when the backend is down so that I know how to fix the problem.

### Epic 8: Web UI/UX

**US-8.1** As a user, I want a clear navigation (sidebar or top nav) so that I can move between Dashboard, Stocks, Notifications, and Paper Trading without guessing.

**US-8.2** As a user, I want to open a stock from the list and see sentiment, Reddit mentions, and price in one place so that I can decide quickly.

**US-8.3** As a user, I want the Dashboard to show summary info (e.g. unread count, top symbols) at a glance so that I know what needs attention.

**US-8.4** As a user, I want tables I can sort (e.g. by composite score or sentiment) so that I can focus on the most relevant rows.

**US-8.5** As a user, I want loading and error states (spinners, messages) so that I know when data is updating or when something failed.

**US-8.6** As a user, I want dark/light mode so that I can use the app comfortably in different environments.

**US-8.7** As a user, I want the app to work on my phone (readable, tappable) so that I can check alerts or rankings on the go.

**US-8.8** As a user, I want optional auto-refresh for the Dashboard or notifications so that I see updates without manually reloading.

---

## 7. Technical Architecture

### 7.1 System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│              User Interfaces (Browser + CLI)                     │
│  ┌─────────────────────────┐  ┌──────────────────────────────┐  │
│  │   React Frontend        │  │   CLI (meme-stocks)          │  │
│  │   (Web UI)              │  │   (API client, terminal)     │  │
│  └─────────────────────────┘  └──────────────────────────────┘  │
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
| Frontend | React + TypeScript + Vite | Web user interface |
| CLI | Python (argparse/click/typer) | Terminal interface, API client |
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
| RedditPost | Reddit submissions (source = subreddit + url) | id (PK), subreddit, title, author, upvotes, comments, url, posted_at, collected_at |
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
| DAILY_ANALYSIS_HOUR | 16 | Hour (24h format, UTC) for daily analysis |
| REDDIT_SUBREDDITS | wallstreetbets,stocks,investing | Subreddits to monitor |
| ENABLE_CATCH_UP | true | Run missed jobs on startup |

---

## 9. Assumptions and Constraints

### Assumptions

1. **Users have basic trading knowledge**: The app does not teach trading fundamentals.
2. **Users have their own brokerage**: No broker integration; all trades are manual.
3. **Reddit is a valid signal source**: Social sentiment on Reddit correlates with meme stock movements.
4. **Free APIs are sufficient**: Reddit and Yahoo Finance free tiers meet our data needs.
5. **Single-user application (for now)**: Designed for personal use by one user. No multi-user authentication, tenant isolation, or concurrency requirements. May support multiple users in a future version.

### Data, Time, and API Policy

- **Data retention**: Indefinite. Reddit posts, price data, notifications, and trade history are retained until explicitly removed. No automatic purging.
- **Timezones**: All timestamps and scheduled times use UTC. The `DAILY_ANALYSIS_HOUR` and similar config values are interpreted in UTC.
- **API versioning**: Not used. The API may evolve; breaking changes will be documented in release notes.

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
6. **Options data**: Track options flow and unusual options activity
7. **News integration**: Aggregate news headlines alongside social sentiment
8. **Backtesting engine**: Test strategies against historical data
9. **Discord/Telegram alerts**: Push notifications to messaging platforms

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

See FR-8 "CLI Command Structure" for the mapping between CLI commands and API endpoints.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check |
| GET | /api/stocks | List tracked stocks |
| GET | /api/stocks/{symbol} | Get stock details |
| GET | /api/stocks/{symbol}/sentiment | Get sentiment analysis |
| GET | /api/stocks/{symbol}/mentions | Get recent Reddit mentions for symbol (with source: subreddit, url) |
| GET | /api/stocks/{symbol}/prices | Get price history |
| GET | /api/analysis/daily | Get daily ranked analysis |
| GET | /api/analysis/causal/{symbol} | Get lead-lag evidence (mentions/sentiment vs returns) |
| GET | /api/notifications | List unread notifications |
| POST | /api/trades | Create paper trade |
| GET | /api/trades | List paper trades |
| POST | /api/trades/{id}/close | Close paper trade |
| GET | /api/portfolio | Get portfolio summary |
| POST | /api/symbol-universe/refresh | Refresh symbol whitelist |
| GET | /api/symbol-universe/stats | Get symbol universe stats |

### B. CLI Quick Reference (FR-8)

When implemented, the CLI will support:

```bash
meme-stocks health
meme-stocks stocks list | show SYMBOL | mentions SYMBOL | add SYMBOL
meme-stocks sentiment SYMBOL
meme-stocks prices SYMBOL
meme-stocks analysis
meme-stocks notifications
meme-stocks trades list | create SYMBOL buy|sell QTY PRICE | close ID EXIT_PRICE
meme-stocks portfolio
meme-stocks symbols refresh | stats
meme-stocks jobs reddit | prices | notifications | runs [JOB] | recent-posts
```

Use `meme-stocks --help` and `meme-stocks <command> --help` for details.

### C. Related Documents

- **PLAN.md**: Detailed project plan, architecture, and business logic
- **README.md**: Quick start guide and development instructions
- **.cursorrules**: Development guidelines and coding standards (references PRD §5.0)
- **.cursor/rules/reliability.mdc**: Always-applied rule for AI agents implementing Reliability Principles
- **.cursor/rules/agent-conduct.mdc**: Always-applied rule—be skeptical, don't oversell, verify before claiming
- **docs/SPEC_KIT_USAGE.md**: How to use Spec Kit for spec-driven development in this repo
- **docs/BROWNFIELD_SPEC_KIT.md**: Brownfield context for AI agents creating specs

### D. API Error Response Format

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
