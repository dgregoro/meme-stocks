# Causal / Predictive Research: Reddit Mentions → Stock Price Movement

## Goal

The goal of this research track is to evaluate whether changes in Reddit discussion of a stock
*precede* and help *predict* future price movement — and to do so in a way that avoids common traps:

- look-ahead bias (leakage)
- incorrect time alignment (after-hours posts treated as same-day signals)
- confusing “price reacts → Reddit reacts” with “Reddit leads → price moves”

This document describes the data artifacts and experiment patterns needed to support this goal.

---

## What We Mean by “Causation” Here

We cannot “train causation” directly with standard supervised learning.

Instead, we:

1) Train and evaluate **predictive relationships** (does Reddit improve forward-return forecasts?)
2) Use time-series validation and controls to strengthen causal interpretation

The initial milestone is **credible predictiveness** with leakage-safe datasets.

---

## Required Data Artifacts (Planned)

### 1) Daily Aggregated Reddit Features (per symbol, per day)

We need a deterministic table / dataset that aggregates Reddit activity into daily features per symbol.

Example columns:

- `date`
- `symbol`
- `mention_count`
- `unique_authors`
- `submission_count`
- `comment_count`
- `upvote_weighted_mentions`
- `avg_sentiment` (or multiple sentiment variants)
- `wsb_share` (optional: fraction of mentions from r/wallstreetbets)

Time semantics:

- Define whether this is “calendar day” or “trading day”
- Posts after market close should not be treated as information available during that same trading session

### 2) Forward Return Labels (per symbol, per day)

Define outcomes strictly from future prices:

- `fwd_return_1d`, `fwd_return_5d`, `fwd_return_10d`
- optionally `fwd_excess_return_vs_spy_{horizon}` to de-market the label

These labels must be computed from price data with explicit horizon logic.

### 3) Deterministic Dataset Builder

We need a reproducible dataset builder that:

- joins daily Reddit features with price-derived features (e.g., RSI)
- joins forward-return labels
- enforces “as-of” time constraints
- writes a versioned dataset snapshot (CSV/parquet/table) for repeatability

If two runs use the same inputs and configuration, they should produce identical datasets.

---

## First Experiments (Recommended Order)

### A) Directionality sanity check

Before modeling, test which direction appears stronger:

- `mentions(t-1..t-k) → returns(t+1..t+h)`
- `returns(t-1..t-k) → mentions(t+1..t+h)`

If price leads mentions more strongly than mentions lead price, interpret results accordingly.

### B) Event study (mention spikes)

Define a “mention shock” day, e.g.:

- mention_count > rolling_mean + N * rolling_std
  OR
- mention_count above 95th percentile for that symbol

Then compute average forward returns for shock days vs non-shock days.

### C) Granger-style predictiveness tests (baseline vs augmented)

Compare forecasting performance:

- baseline: uses past returns / technicals only
- augmented: baseline + Reddit features

If augmented improves out-of-sample metrics with time-based splits, that is evidence of predictiveness.

---

## Leakage / Alignment Rules (Non-Negotiable)

1) **No future features**
   - Features for date D must be constructed only from information available at or before the chosen “as-of” cutoff.

2) **After-hours handling**
   - Define a consistent rule for posts after market close (typically count toward next trading day features).

3) **Time-based splits only**
   - No random train/test split for time series.
   - Use time-based split or walk-forward evaluation.

4) **Controls**
   - Consider controls like market return, sector proxies, volatility, and volume
   - Avoid attributing broad-market moves to Reddit

---

## What “Done” Looks Like for This Track

Minimum viable research capability:

- A daily aggregated Reddit features dataset per symbol
- Forward-return labels
- A dataset builder command/module that generates reproducible snapshots
- At least one baseline + augmented model comparison with time-based evaluation

Once this foundation exists, we can iterate on richer NLP features and more advanced models.

