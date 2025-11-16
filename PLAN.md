# Meme Stocks Trading Application - Project Plan

## Project Overview
A web application for analyzing meme stocks using social sentiment (Reddit) and price patterns. The app supports manual trading decisions with end-of-day analysis and real-time notifications for unusual activity. Includes paper trading/modeling capabilities.

## Core Requirements

### Functional Requirements
1. **Social Sentiment Analysis**
   - Reddit data collection and analysis
   - Sentiment scoring for stocks mentioned
   - Track mentions, upvotes, comment volume

2. **Price Pattern Analysis**
   - Historical price data from Yahoo Finance
   - Pattern recognition and technical indicators
   - Price movement analysis

3. **End-of-Day Analysis**
   - Daily summary reports
   - Stock screening based on criteria
   - Historical trend analysis

4. **Real-Time Notifications**
   - Unusual activity alerts (volume spikes, price movements, sentiment shifts)
   - Configurable notification thresholds
   - Notification history

5. **Paper Trading/Modeling**
   - Track hypothetical positions
   - Portfolio simulation
   - Performance tracking
   - Trade history

### Non-Functional Requirements
- **Code Quality**: Easily refactored, modular architecture
- **Error Handling**: Explicit errors, no silent failures
- **Data Sources**: Free APIs only (Reddit, Yahoo Finance)
- **Technology**: Python backend, web frontend
- **No Broker Integration**: All trading is manual/external

## Milestones

- **Milestone 0 – Foundations & Test Framework** (**completed**)
  FastAPI skeleton, config module, pytest + basic tests.

- **Milestone 1 – Data Layer & Models** (**completed**)
  SQLAlchemy models (Stock, RedditPost, PriceData) and repositories with DB tests.

- **Milestone 2 – Data Ingestion** (**completed**)
  Reddit and Yahoo data services (no direct DB coupling) with mocked external API tests.

- **Milestone 3 – Analysis Engine** (**completed**)
  Sentiment analyzer, price trend analyzer, and unusual activity detector implemented as pure, testable functions with configurable thresholds.

- **Milestone 4 – API & Backend (current)**
  - First slice:
    - `GET /api/stocks` and `GET /api/stocks/{symbol}` using repositories.
    - `GET /api/stocks/{symbol}/sentiment` using Reddit posts + sentiment analyzer.
    - `GET /api/stocks/{symbol}/prices` using stored price data.
  - Later slices: analysis summary endpoint, notifications API, and paper trading API, plus WebSocket notifications.

- **Milestone 5 – Frontend MVP**
  Dashboard, stock detail views, notifications panel, and paper trading UI.

- **Milestone 6 – Background Jobs & Refinement**
  Schedulers for data collection and EOD analysis, performance optimizations, and UX polish.

## Architecture

### High-Level Architecture
```
┌─────────────────┐
│   Web Frontend  │ (React/Vue or simple HTML/JS)
└────────┬────────┘
         │
┌────────▼────────┐
│  Python Backend │ (FastAPI/Flask)
│  - API Routes   │
│  - Business Logic│
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼────┐
│ Data  │ │ Data  │
│Layer  │ │Storage│
│       │ │       │
│Reddit │ │SQLite │
│Yahoo  │ │/JSON  │
└───────┘ └───────┘
```

### Technology Stack

#### Backend
- **Framework**: FastAPI (modern, async, auto-docs)
- **Data Processing**: pandas, numpy
- **Reddit API**: PRAW (Python Reddit API Wrapper)
- **Yahoo Finance**: yfinance library
- **Database**: SQLite (simple, file-based, no setup needed)
- **Task Scheduling**: APScheduler (for periodic data collection)
- **WebSockets**: FastAPI WebSocket support (for real-time notifications)

#### Frontend
- **Framework**: React (or vanilla JS for simplicity)
- **UI Library**: Tailwind CSS or Material-UI
- **Charts**: Chart.js or Plotly.js
- **State Management**: React Context or simple state

#### Development Tools
- **Package Management**: Poetry or pip + requirements.txt
- **Code Quality**: black, flake8, mypy
- **Testing**: pytest
- **Environment**: python-dotenv

## Project Structure

```
meme-stocks/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── config.py            # Configuration management
│   │   ├── models/              # Data models (Pydantic/SQLAlchemy)
│   │   │   ├── __init__.py
│   │   │   ├── stock.py
│   │   │   ├── sentiment.py
│   │   │   └── trade.py
│   │   ├── api/                 # API routes
│   │   │   ├── __init__.py
│   │   │   ├── stocks.py
│   │   │   ├── sentiment.py
│   │   │   ├── analysis.py
│   │   │   ├── notifications.py
│   │   │   └── paper_trading.py
│   │   ├── services/            # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── reddit_service.py
│   │   │   ├── yahoo_service.py
│   │   │   ├── sentiment_analyzer.py
│   │   │   ├── pattern_analyzer.py
│   │   │   └── notification_service.py
│   │   ├── data/                # Data access layer
│   │   │   ├── __init__.py
│   │   │   ├── database.py
│   │   │   └── repositories/
│   │   │       ├── stock_repo.py
│   │   │       ├── sentiment_repo.py
│   │   │       └── trade_repo.py
│   │   └── utils/               # Utilities
│   │       ├── __init__.py
│   │       ├── errors.py        # Custom exceptions
│   │       └── validators.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_services/
│   │   └── test_api/
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/            # API client
│   │   ├── utils/
│   │   └── App.js
│   ├── package.json
│   └── public/
├── data/                        # SQLite DB, cached data
├── logs/                        # Application logs
├── PLAN.md                      # This file
├── README.md
└── .gitignore
```

## Trading Strategies & Business Logic

### Core Trading Strategies

The application will identify trading opportunities using three primary strategies:

#### 1. Sentiment Momentum Strategy
**Objective**: Identify stocks gaining traction in social media before price movement

**Business Logic**:
- **Sentiment Score Calculation**:
  - Aggregate sentiment from Reddit posts mentioning the stock
  - Weight by engagement: `weight = log(upvotes + comments + 1)`
  - Score range: -1 (very negative) to +1 (very positive)
  - Formula: `sentiment_score = weighted_average(post_sentiments)`

- **Momentum Detection**:
  - Track sentiment change over time windows (1h, 4h, 24h)
  - Calculate momentum: `momentum = (current_sentiment - previous_sentiment) / time_delta`
  - Identify accelerating momentum: `acceleration = momentum_change_rate`

- **Signal Generation**:
  - **Bullish Signal**: Sentiment > 0.3 AND momentum > 0.1 AND mention_count increasing
  - **Bearish Signal**: Sentiment < -0.2 AND momentum < -0.1
  - **Neutral**: Sentiment between -0.2 and 0.3

#### 2. Price Pattern Breakout Strategy
**Objective**: Identify technical breakouts and reversals

**Business Logic**:
- **Technical Indicators**:
  - **SMA (Simple Moving Average)**: 20-day and 50-day
  - **RSI (Relative Strength Index)**: 14-period
  - **Volume Analysis**: Compare current volume to 20-day average
  - **Price Channels**: Identify support/resistance levels

- **Pattern Detection**:
  - **Breakout Above Resistance**: Price breaks above recent high with volume > 1.5x average
  - **Breakdown Below Support**: Price breaks below recent low with volume > 1.5x average
  - **RSI Divergence**: Price makes new high/low but RSI doesn't (potential reversal)
  - **Volume Spike**: Volume > 2x average (potential accumulation/distribution)

- **Signal Generation**:
  - **Bullish**: Price > SMA20 > SMA50 AND RSI > 50 AND volume increasing
  - **Bearish**: Price < SMA20 < SMA50 AND RSI < 50 AND volume increasing
  - **Reversal Alert**: RSI divergence detected

#### 3. Combined Sentiment-Price Strategy
**Objective**: Find stocks where sentiment and price patterns align

**Business Logic**:
- **Alignment Scoring**:
  - Calculate alignment score: `alignment = sentiment_score * price_trend`
  - Where `price_trend` = +1 (uptrend), -1 (downtrend), 0 (sideways)

- **Signal Strength**:
  - **Strong Buy**: Positive sentiment + bullish price pattern + high volume
  - **Strong Sell**: Negative sentiment + bearish price pattern + high volume
  - **Weak Signal**: Sentiment and price patterns conflict

- **Confidence Score**:
  ```
  confidence = (sentiment_strength * 0.4) + (price_pattern_strength * 0.4) + (volume_confirmation * 0.2)
  ```
  - Range: 0 to 1
  - Higher confidence = stronger signal

### Business Logic Details

#### Sentiment Analysis Logic

**Post Sentiment Scoring**:
1. **Text Analysis**:
   - Use simple keyword-based sentiment (can be upgraded to ML later)
   - Positive keywords: "buy", "moon", "hold", "bullish", "gains", "profit"
   - Negative keywords: "sell", "crash", "bearish", "loss", "dump", "scam"
   - Neutral: Default if no strong indicators

2. **Engagement Weighting**:
   - Higher engagement = more reliable signal
   - Formula: `weight = log10(upvotes + comments + 1)`
   - Prevents single high-engagement post from dominating

3. **Time Decay**:
   - Recent posts weighted more heavily
   - Decay factor: `weight *= exp(-hours_old / 24)`
   - Posts older than 7 days have minimal weight

**Aggregate Sentiment Calculation**:
```python
def calculate_sentiment_score(stock_symbol, time_window='24h'):
    posts = get_posts_in_window(stock_symbol, time_window)

    if not posts:
        return None  # Explicit: no data = no score

    total_weighted_sentiment = 0
    total_weight = 0

    for post in posts:
        post_sentiment = analyze_post_sentiment(post.text)
        engagement_weight = log10(post.upvotes + post.comments + 1)
        time_weight = exp(-post.hours_old / 24)
        weight = engagement_weight * time_weight

        total_weighted_sentiment += post_sentiment * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0  # Explicit: avoid division by zero

    return total_weighted_sentiment / total_weight
```

#### Price Pattern Analysis Logic

**Technical Indicator Calculations**:
1. **Moving Averages**:
   - SMA20: Average of last 20 closing prices
   - Used to identify trend direction
   - Price above SMA = uptrend, below = downtrend

2. **RSI Calculation**:
   ```
   RSI = 100 - (100 / (1 + RS))
   RS = Average Gain / Average Loss (over 14 periods)
   ```
   - RSI > 70: Overbought (potential sell)
   - RSI < 30: Oversold (potential buy)
   - RSI 50: Neutral

3. **Volume Analysis**:
   - Calculate 20-day average volume
   - Current volume ratio: `volume_ratio = current_volume / avg_volume`
   - Volume spike: `volume_ratio > 1.5`
   - Volume confirmation: High volume validates price movement

**Pattern Detection Rules**:
```python
def detect_price_pattern(price_data):
    """
    Returns: pattern_type, confidence, direction
    """
    sma20 = calculate_sma(price_data, 20)
    sma50 = calculate_sma(price_data, 50)
    rsi = calculate_rsi(price_data, 14)
    volume_ratio = current_volume / avg_volume_20d

    # Breakout pattern
    if price > resistance_level and volume_ratio > 1.5:
        return "breakout", 0.8, "bullish"

    # Breakdown pattern
    if price < support_level and volume_ratio > 1.5:
        return "breakdown", 0.8, "bearish"

    # Trend continuation
    if price > sma20 > sma50 and rsi > 50:
        return "uptrend", 0.6, "bullish"

    if price < sma20 < sma50 and rsi < 50:
        return "downtrend", 0.6, "bearish"

    return "sideways", 0.3, "neutral"
```

#### Unusual Activity Detection Logic

**Alert Conditions** (all thresholds configurable):

1. **Volume Spike Alert**:
   ```python
   if current_volume > (avg_volume_20d * VOLUME_SPIKE_THRESHOLD):
       create_notification(
           type="volume_spike",
           severity="high" if volume_ratio > 3.0 else "medium",
           message=f"{symbol} volume {volume_ratio:.1f}x average"
       )
   ```
   - Default threshold: 2.0x average volume
   - High severity: > 3.0x average

2. **Price Movement Alert**:
   ```python
   price_change_pct = (current_price - previous_close) / previous_close * 100

   if abs(price_change_pct) > PRICE_MOVEMENT_THRESHOLD:
       create_notification(
           type="price_movement",
           severity="high" if abs(price_change_pct) > 10 else "medium",
           message=f"{symbol} moved {price_change_pct:.2f}%"
       )
   ```
   - Default threshold: ±5% intraday
   - High severity: ±10%

3. **Sentiment Shift Alert**:
   ```python
   sentiment_change = current_sentiment - sentiment_24h_ago

   if abs(sentiment_change) > SENTIMENT_SHIFT_THRESHOLD:
       direction = "positive" if sentiment_change > 0 else "negative"
       create_notification(
           type="sentiment_shift",
           severity="high" if abs(sentiment_change) > 0.5 else "medium",
           message=f"{symbol} sentiment shifted {direction}"
       )
   ```
   - Default threshold: ±0.3 sentiment points
   - High severity: ±0.5

4. **Combined Signal Alert**:
   ```python
   if alignment_score > COMBINED_SIGNAL_THRESHOLD and confidence > 0.7:
       create_notification(
           type="strong_signal",
           severity="high",
           message=f"{symbol} strong {direction} signal (confidence: {confidence:.2f})"
       )
   ```
   - Triggers when sentiment and price patterns align strongly

#### End-of-Day Analysis Logic

**Daily Summary Generation**:

1. **Stock Ranking Algorithm**:
   ```python
   def rank_stocks(stocks, date):
       rankings = []

       for stock in stocks:
           # Get latest data
           sentiment = get_latest_sentiment(stock.symbol)
           price_data = get_price_data(stock.symbol, date)
           patterns = detect_price_pattern(price_data)

           # Calculate composite score
           sentiment_score = normalize(sentiment.score, -1, 1)  # 0-1 range
           price_score = calculate_price_score(patterns)  # 0-1 range
           volume_score = normalize(volume_ratio, 0, 3)  # 0-1 range

           composite_score = (
               sentiment_score * 0.4 +
               price_score * 0.4 +
               volume_score * 0.2
           )

           rankings.append({
               'symbol': stock.symbol,
               'score': composite_score,
               'sentiment': sentiment.score,
               'price_trend': patterns.direction,
               'confidence': calculate_confidence(sentiment, patterns)
           })

       return sorted(rankings, key=lambda x: x['score'], reverse=True)
   ```

2. **Analysis Categories**:
   - **Top Opportunities**: Stocks with composite score > 0.7
   - **Watchlist**: Stocks with score 0.5-0.7
   - **Avoid**: Stocks with score < 0.3
   - **High Risk**: High volatility + low confidence

3. **Trend Analysis**:
   - Compare today's metrics to 7-day average
   - Identify improving/declining trends
   - Flag significant changes (>20% difference)

#### Paper Trading Logic

**Position Management**:
1. **Trade Entry**:
   - User specifies: symbol, quantity, entry price, notes
   - System validates: symbol exists, price is valid, quantity > 0
   - Creates trade record with timestamp

2. **Position Tracking**:
   - Calculate unrealized P/L: `(current_price - entry_price) * quantity`
   - Track position value: `current_price * quantity`
   - Update in real-time as prices change

3. **Performance Metrics**:
   - Total P/L: Sum of all closed positions + unrealized P/L
   - Win rate: `wins / total_trades`
   - Average win/loss: Average of winning vs losing trades
   - Best/worst trade: Highest and lowest P/L

4. **Trade Closure**:
   - User closes position: specify exit price
   - Calculate realized P/L
   - Update performance metrics

### Decision Rules Summary

**When to Flag a Stock for Review**:
1. Sentiment score > 0.3 AND increasing momentum
2. Price breaks above resistance with volume confirmation
3. RSI < 30 (oversold) AND positive sentiment
4. Volume spike > 2x average
5. Combined alignment score > 0.6 with confidence > 0.7

**When to Alert (Real-time)**:
1. Volume spike > 2x average
2. Price movement > ±5% intraday
3. Sentiment shift > ±0.3 points in 24h
4. Strong combined signal (alignment > 0.6, confidence > 0.7)

**When to Include in Daily Analysis**:
1. Has sufficient data (min 10 Reddit mentions OR price data available)
2. Meets minimum activity threshold (volume > 100k shares)
3. Not excluded by user filters

### Configuration & Thresholds

All thresholds should be configurable via environment variables or config file:
- `SENTIMENT_POSITIVE_THRESHOLD` (default: 0.3)
- `SENTIMENT_NEGATIVE_THRESHOLD` (default: -0.2)
- `VOLUME_SPIKE_THRESHOLD` (default: 2.0)
- `PRICE_MOVEMENT_THRESHOLD` (default: 5.0%)
- `SENTIMENT_SHIFT_THRESHOLD` (default: 0.3)
- `COMBINED_SIGNAL_THRESHOLD` (default: 0.6)
- `MIN_CONFIDENCE_THRESHOLD` (default: 0.7)

## Feature Breakdown

### Phase 1: Core Data Collection
1. **Reddit Integration**
   - Set up PRAW client
   - Monitor specific subreddits (r/wallstreetbets, r/stocks, etc.)
   - Extract stock mentions (ticker symbols)
   - Collect metadata (upvotes, comments, timestamp)
   - Store in database

2. **Yahoo Finance Integration**
   - Fetch historical price data
   - Fetch real-time quotes
   - Store price data
   - Handle rate limiting and errors

3. **Database Schema**
   - Stocks table (symbol, name, sector, etc.)
   - Reddit posts table
   - Sentiment scores table
   - Price data table
   - Notifications table
   - Paper trades table

### Phase 2: Analysis Engine
1. **Sentiment Analysis**
   - Basic sentiment scoring (positive/negative/neutral)
   - Aggregate sentiment per stock
   - Sentiment trends over time
   - Volume of mentions

2. **Price Pattern Analysis**
   - Basic technical indicators (SMA, RSI, volume)
   - Pattern detection (breakouts, reversals)
   - Price movement classification
   - Historical comparison

3. **Unusual Activity Detection**
   - Volume spike detection
   - Price movement thresholds
   - Sentiment shift detection
   - Configurable alert rules

### Phase 3: API & Backend
1. **REST API Endpoints**
   - GET /api/stocks - List stocks
   - GET /api/stocks/{symbol} - Stock details
   - GET /api/stocks/{symbol}/sentiment - Sentiment data
   - GET /api/stocks/{symbol}/price - Price data
   - GET /api/analysis/daily - End-of-day analysis
   - GET /api/notifications - Get notifications
   - WebSocket /ws/notifications - Real-time notifications

2. **Paper Trading API**
   - POST /api/trades - Create paper trade
   - GET /api/trades - List trades
   - GET /api/portfolio - Portfolio summary
   - DELETE /api/trades/{id} - Close position

### Phase 4: Frontend
1. **Dashboard**
   - Overview of tracked stocks
   - Recent sentiment scores
   - Price charts
   - Active notifications

2. **Stock Detail Page**
   - Price chart with indicators
   - Sentiment timeline
   - Reddit mentions list
   - Analysis summary

3. **Daily Analysis Page**
   - End-of-day summary
   - Stock rankings
   - Filterable/sortable tables

4. **Paper Trading Interface**
   - Trade entry form
   - Portfolio view
   - Performance metrics
   - Trade history

5. **Notifications Panel**
   - Real-time notification stream
   - Notification history
   - Filter by type/stock

### Phase 5: Background Jobs
1. **Scheduled Tasks**
   - Periodic Reddit data collection
   - Price data updates
   - End-of-day analysis generation
   - Notification checks

## Data Models

### Stock
- symbol (string, primary key)
- name (string)
- sector (string, nullable)
- market_cap (float, nullable)
- created_at (datetime)
- updated_at (datetime)

### RedditPost
- id (string, primary key)
- stock_symbol (string, foreign key)
- subreddit (string)
- title (string)
- author (string)
- upvotes (integer)
- comments (integer)
- url (string)
- posted_at (datetime)
- collected_at (datetime)

### SentimentScore
- id (integer, primary key)
- stock_symbol (string, foreign key)
- score (float)  # -1 to 1
- mention_count (integer)
- calculated_at (datetime)
- period (string)  # 'hourly', 'daily', etc.

### PriceData
- id (integer, primary key)
- stock_symbol (string, foreign key)
- date (date)
- open (float)
- high (float)
- low (float)
- close (float)
- volume (integer)
- timestamp (datetime)

### Notification
- id (integer, primary key)
- stock_symbol (string, foreign key)
- type (string)  # 'volume_spike', 'price_movement', 'sentiment_shift'
- message (string)
- severity (string)  # 'low', 'medium', 'high'
- created_at (datetime)
- read (boolean)

### PaperTrade
- id (integer, primary key)
- stock_symbol (string, foreign key)
- action (string)  # 'buy', 'sell'
- quantity (integer)
- price (float)
- executed_at (datetime)
- notes (string, nullable)

## Error Handling Strategy

### Principles
1. **Explicit Errors**: All errors must be logged and returned to user
2. **No Silent Failures**: If data fetch fails, return error, don't return empty data
3. **Validation**: Validate all inputs at API boundaries
4. **Type Safety**: Use type hints throughout (mypy)

### Error Types
- `DataFetchError`: When external API calls fail
- `ValidationError`: When input validation fails
- `NotFoundError`: When requested resource doesn't exist
- `DatabaseError`: When database operations fail

### Error Response Format
```json
{
  "error": true,
  "error_type": "DataFetchError",
  "message": "Failed to fetch data from Yahoo Finance",
  "details": {...}
}
```

## Configuration Management

### Environment Variables
- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `REDDIT_USER_AGENT`
- `DATABASE_URL` (default: sqlite:///data/app.db)
- `LOG_LEVEL` (default: INFO)
- `API_HOST` (default: localhost)
- `API_PORT` (default: 8000)

## Development Workflow

### Phase 1: Setup & Infrastructure
1. Initialize project structure
2. Set up Python environment
3. Create database schema
4. Set up basic FastAPI app
5. Create configuration management

### Phase 2: Data Collection
1. Implement Reddit service
2. Implement Yahoo Finance service
3. Create database repositories
4. Add data collection scheduling

### Phase 3: Analysis
1. Implement sentiment analyzer
2. Implement pattern analyzer
3. Create unusual activity detector
4. Build end-of-day analysis

### Phase 4: API Development
1. Create all API endpoints
2. Add WebSocket support
3. Implement error handling
4. Add API documentation

### Phase 5: Frontend
1. Set up React app
2. Create API client
3. Build dashboard
4. Build stock detail page
5. Build paper trading interface
6. Add real-time notifications

### Phase 6: Testing & Refinement
1. Write unit tests
2. Integration testing
3. Error handling verification
4. Performance optimization
5. UI/UX improvements

## Success Criteria

### MVP (Minimum Viable Product)
- [ ] Can collect Reddit data for specified stocks
- [ ] Can fetch price data from Yahoo Finance
- [ ] Basic sentiment scoring works
- [ ] Can view stock data in web interface
- [ ] Can create paper trades
- [ ] Basic notifications work

### Full Feature Set
- [ ] All data sources integrated
- [ ] Complete analysis engine
- [ ] Full API with documentation
- [ ] Complete frontend with all pages
- [ ] Real-time notifications
- [ ] End-of-day analysis reports
- [ ] Paper trading with performance tracking

## Risks & Considerations

1. **API Rate Limits**: Reddit and Yahoo Finance have rate limits
   - Solution: Implement caching and rate limit handling

2. **Data Quality**: Free APIs may have inconsistent data
   - Solution: Validate data, handle missing fields gracefully

3. **Sentiment Analysis Accuracy**: Basic sentiment may not be perfect
   - Solution: Start simple, make it configurable for future improvements

4. **Real-time Performance**: WebSocket connections and real-time updates
   - Solution: Use async/await, efficient database queries

5. **Scalability**: SQLite may not scale for large datasets
   - Solution: Design for easy migration to PostgreSQL later

## Tech Debt & Future Improvements

This section tracks intentional shortcuts and areas to revisit later. Items here should be turned into concrete tasks when we enter the relevant milestone.

### Current Tech Debt

- **Sentiment analysis (Milestone 3)**
  - Uses a simple, hard-coded keyword list for positive/negative terms and only analyzes the post title.
  - Future work: move keywords into configuration, incorporate post body where available, and optionally plug in a more robust ML-based sentiment model.

- **Price pattern analysis (Milestone 3)**
  - Currently only uses short/long simple moving averages on closing prices to classify trends.
  - Future work: add additional indicators (RSI, volume-based confirmation) and more nuanced pattern recognition.

- **Unusual activity detection (Milestone 3)**
  - Only considers volume ratio, simple price move percent, and scalar sentiment shift; does not yet combine signals into a single composite alert.
  - Future work: implement combined-signal alerts as described in the Trading Strategies & Business Logic section, and expose per-signal thresholds more granularly if needed.

- **Time handling & UTC (tests and services)**
  - Some components still use `datetime.utcnow()` either in code or tests, which raises deprecation warnings and mixes naive vs timezone-aware datetimes.
  - Future work: standardize on timezone-aware `datetime.now(datetime.UTC)` throughout services and tests, and ensure DB models and external data are consistent.

- **Reddit ticker extraction**
  - `RedditPostData.stock_symbol` is currently left as an empty string in the ingestion service; actual ticker extraction logic is not yet implemented.
  - Future work: implement a dedicated ticker extraction module with clear rules and tests (e.g., regex-based detection, allowed-ticker lists).

## Next Steps

1. Review and approve this plan
2. Set up project structure
3. Begin Phase 1 implementation
4. Iterate based on feedback

---

**Note**: This plan is designed to be iterative. We can adjust features and priorities as we build and learn.
