# Meme Stocks - Business Logic & Algorithms

This document details the trading strategies, scoring algorithms, and business logic used by the application.

**Related Documentation:**
- `PRD.md` - Product requirements and feature status
- `ARCHITECTURE.md` - Implementation patterns
- `ROADMAP.md` - Future development work
- `STRATEGY_EXPLORATION.md` - Daily-frequency research ideas and result log (no Reddit / no intraday)
- `README.md` - Quick start guide

---

## Two Tracks: Decision Support vs. Causal Research

This repo currently implements **decision-support heuristics** (alerts, rankings, paper trading) and
also tracks a **research direction** focused on whether Reddit mention activity precedes and predicts
future price movement.

### A) Decision-Support Track (Current)

This is the implemented “product” behavior:

- Collect Reddit + price data
- Compute features (sentiment, SMA-based patterns, RSI)
- Generate alerts + end-of-day ranked analysis
- Support paper trading and portfolio tracking

This track can be heuristic-driven and does not require formal training pipelines.

### B) Causal / Predictive Research Track (Implemented)

Goal: build leakage-safe datasets and run time-series experiments that answer:

- Do Reddit mentions lead price (predictive relationship)?
- Is the relationship robust after controls (market/sector/volatility/volume)?
- Is the directionality reversed (price → mentions)?

Implemented:

- **Daily aggregated Reddit features per symbol** — `RedditDailyFeature`, `reddit_daily_feature_service`
- **Forward-return labels** — `PriceLabel`, horizons 1/5/10, `label_service`
- **Deterministic dataset builder** — `dataset_builder_service`, metadata sidecar, CLI `build-dataset`
- **Experiment runners** — directionality, event-study, predictiveness (CLI `experiment`)

See: `docs/CAUSAL_RESEARCH.md`

---

## Implementation Status

All milestones (M0-M7) are complete. See `PRD.md` Section 13 for detailed milestone descriptions.

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

---

**Note**: For data models, API endpoints, error handling patterns, and configuration details, see:
- `PRD.md` - Requirements and data models
- `ARCHITECTURE.md` - Implementation patterns
- `GETTING_STARTED.md` - Configuration reference
- `ROADMAP.md` - Future work and tech debt tracking
