# Causal / Predictive Research: Reddit Mentions → Stock Price Movement

**Operational status (March 2026):** This document describes the **methodology** that motivated early work (**social mentions vs price**). **Reddit ingestion has been removed** from the application; daily “Reddit” feature columns in datasets may be **zeros** or omitted. **Price, labels, and time-series hygiene** (no look-ahead, correct horizons) remain relevant; replace “Reddit” mentally with **any future text feed** or use **price-only** variants of the same checks.

## Goal

The goal of this research track is to evaluate whether changes in Reddit discussion of a stock
*precede* and help *predict* future price movement — and to do so in a way that avoids common traps:

- look-ahead bias (leakage)
- incorrect time alignment (after-hours posts treated as same-day signals)
- confusing “price reacts → Reddit reacts” with “Reddit leads → price moves”

This document describes the data artifacts and experiment patterns needed to support this goal.
Daily features are assigned based on **posted_at** in the market timezone (with after-hours rules), *not* on
collected_at, to avoid collection-lag distortion and look-ahead leakage.

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

---

## Implementation Status

The following artifacts and experiments are implemented:

### Data Artifacts

1. **Daily Reddit Features** — `RedditDailyFeature` model, `reddit_daily_feature_service.compute_and_store_reddit_daily_features()`. Uses `posted_at` with market-timezone after-hours rules.

2. **Forward Return Labels** — `PriceLabel` model, `label_service.compute_and_store_forward_returns()`. Horizons 1, 5, 10 in **trading days** (sessions), not calendar days. Leakage-safe: only when both close[D] and close[target] exist.

3. **Dataset Builder** — `dataset_builder_service.build_training_dataset()`. INNER JOIN features + labels, deterministic row/column order, metadata sidecar JSON. CLI: `python -m backend.app.cli build-dataset --start YYYY-MM-DD --end YYYY-MM-DD --horizon 5 --out path.csv`

### Experiments

- **Directionality** — `experiments/directionality.run_directionality()`. CLI: `python -m backend.app.cli experiment directionality --dataset path.csv --k 5 --h 1`
- **Event Study** — `experiments/event_study.run_event_study()`. CLI: `python -m backend.app.cli experiment event-study --dataset path.csv --window 20 --threshold p95 --horizon 5`
- **Predictiveness** — `experiments/predictiveness.run_predictiveness()`. CLI: `python -m backend.app.cli experiment predictiveness --dataset path.csv --horizon 5 --split-date YYYY-MM-DD`
