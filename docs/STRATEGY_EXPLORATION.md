# Daily-frequency strategy exploration log

This document tracks **non-Reddit, daily (or lower) frequency** ideas for systematic exploration: definitions, data needs, difficulty to test, and a running log of results.

**Constraints (for this list):**

- No social / Reddit features.
- No intraday bars or session-internal logic (only daily—or coarser—series).
- Treat every result as provisional until it passes `docs/SIGNAL_EVALUATION_CHECKLIST.md`.

**Related docs:**

- `docs/SIGNAL_EVALUATION_CHECKLIST.md` — minimum bar before believing an edge.
- `docs/CAUSAL_RESEARCH.md` — leakage-safe dataset and experiment patterns (adapt features to daily price/volume only).
- `docs/PLAN.md` — implemented product logic vs. research tracks.

---

## Summary table

| ID | Strategy (short name)                          | Test difficulty (1 = easiest) | Primary data                                            |
| -- | ----------------------------------------------- | ----------------------------: | ------------------------------------------------------- |
| S1 | Volume vs. realized-vol mismatch                |                             1 | Daily OHLCV                                             |
| S2 | Gap ecology (daily OHLC)                        |                             2 | Daily OHLC (open vs prior close)                        |
| S3 | Volatility term structure regime                |                             3 | Daily VIX + medium-term vol (e.g. VIX3M) + equity returns |
| S4 | Calendar / scheduled event skeleton             |                             4 | Daily returns + calendar flags                          |
| S5 | Cross-sectional dispersion                      |                             5 | Panel of daily returns + universe definition            |
| S6 | Slow pairs / relative value (cointegration-style) |                             6 | Two (or few) daily return series + corporate actions    |
| S7 | Rule discovery on daily features                |                             7 | Daily features + strict OOS / complexity control        |

---

## Global run log (fill in as you go)

Append a row per meaningful run (backtest, ablation, or formal experiment). Use one row per **strategy ID + universe + key spec** so you can compare over time.

| Run date   | Strategy ID | Universe / tickers | Horizon(s) | Train / test split        | Verdict (kill / maybe / pursue) | Links / notes (commit, notebook, CLI command) |
| ---------- | ----------- | ------------------ | ---------- | ------------------------- | --------------------------------- | ---------------------------------------------- |
| YYYY-MM-DD | S1          |                    |            |                           |                                   |                                                |

**Verdict definitions:**

- **Kill** — fails checklist, wrong sign OOS, or not economically plausible after costs.
- **Maybe** — passes some checks; needs pre-registered refinement or more data.
- **Pursue** — stable OOS, passes checklist; ready for paper / risk review.

---

## S1 — Volume vs. realized-vol mismatch

**Idea:** Compare **rolling realized volatility** of daily returns to **volume** (e.g., volume z-score vs. its own history). Days where variance and volume are **inconsistent** may correspond to different forward return profiles (liquidity vs. one-sided flow).

**Features (examples):**

- Realized vol: stdev of log returns over window \(W_r\) (e.g. 5, 10, 20).
- Volume z-score: \(\log(vol)\) or raw vol standardized over \(W_v\).
- Flags: high vol / low volume, low vol / high volume (thresholds vs. cross-sectional ranks if multi-name).

**Hypotheses to fork (pre-specify one primary):**

- H1: “High vol, low volume” predicts **mean reversion** over \(h\) days.
- H2: “Low vol, high volume” predicts **continuation** or **breakout** over \(h\) days.

**Test difficulty:** 1 (single-symbol or small universe; minimal alignment).

**Results for S1**

| Date       | Spec (windows, thresholds) | Horizon | N events | Checklist OK? | Verdict | Notes |
| ---------- | -------------------------- | ------- | -------: | ------------- | ------- | ----- |
|            |                            |         |          |               |         |       |

---

## S2 — Gap ecology (daily OHLC only)

**Idea:** Classify **overnight gaps** using only daily OHLC: gap vs. prior close, vs. prior day range, and direction relative to a slow trend (e.g. close vs. MA). Hypothesis: **next-day / next-week** expectancy differs by gap **type**, not just “gap up.”

**Features (examples):**

- Gap return: \(\log(O_t / C_{t-1})\) (or simple %).
- Prior range: \(H_{t-1} - L_{t-1}\) vs. gap size.
- Trend bucket: \(C_{t-1}\) above/below MA\(_k\).

**Hypotheses to fork:**

- H1: Small gaps **with** trend → continuation.
- H2: Large gaps **against** trend → fade.
- H3: Gap size as fraction of prior true range drives bucket outcomes.

**Test difficulty:** 2 (more degrees of freedom in buckets; watch multiple testing).

**Results for S2**

| Date       | MA period / bucket defs | Horizon | N per bucket (min) | Checklist OK? | Verdict | Notes |
| ---------- | ----------------------- | ------- | ------------------ | ------------- | ------- | ----- |
|            |                         |         |                    |               |         |       |

---

## S3 — Volatility term structure regime

**Idea:** Use **daily** implied vol term shape (e.g. **VIX vs. VIX3M**) to label **regimes** (backwardation vs. contango). Attach **different** equity rules (e.g. exposure, long-only vs. hedge, or factor tilt) per regime—not signals from VIX **level** alone.

**Features (examples):**

- Spread: VIX − VIX3M (or ratio); percentile over history.
- Regime: \(q\) buckets or HMM-style labels (keep simple first).

**Hypotheses to fork:**

- H1: Steep backwardation → favor **defensive** or lower beta; contango → opposite.
- H2: Regime **change** days (not level) drive short-horizon equity drift.

**Test difficulty:** 3 (extra series; threshold sensitivity).

**Results for S3**

| Date       | Regime definition | Equity rule tested | Horizon | Checklist OK? | Verdict | Notes |
| ---------- | ----------------- | ------------------ | ------- | ------------- | ------- | ----- |
|            |                   |                    |         |               |         |       |

---

## S4 — Calendar / scheduled event skeleton

**Idea:** Test **known dates** (month/quarter turn, OpEx **week** as a calendar flag, pre/post holiday weeks, FOMC week if you maintain a flag) on **daily** returns only. Effects are often **small**; any edge should be **pre-registered** (which flags, which conditioning) to limit data mining.

**Features (examples):**

- Binary: `is_opex_week`, `is_month_end`, `is_fomc_week`, etc.
- Conditioning: interact with vol percentile or trend (reduces degrees of freedom if chosen upfront).

**Hypotheses to fork:**

- H1: OpEx week + high realized vol → distinct return distribution.
- H2: Quarter-end only in up markets → specific tilt (example only; validate, do not trust).

**Test difficulty:** 4 (easy to code; **hard** to interpret without multiple-test discipline).

**Results for S4**

| Date       | Calendar flags (pre-registered set) | Conditioning   | Horizon | Checklist OK? | Verdict | Notes |
| ---------- | ------------------------------------ | -------------- | ------- | ------------- | ------- | ----- |
|            |                                      |                |         |               |         |       |

---

## S5 — Cross-sectional dispersion

**Idea:** Within a sector or peer set, compute **cross-sectional standard deviation** of **daily** returns. After **dispersion spikes**, test mean reversion in **relative** returns (long underperformers vs. short outperformers) vs. **momentum** in the winner—run as **opposing** preregistered forks.

**Features (examples):**

- \(D_t\) = cross-sectional std of peer returns on day \(t\).
- Signal: \(D_t\) > percentile(D, p) (or z-score vs. history).

**Data needs:** Aligned panel; clear **universe** rules (liquidity, adj. for splits).

**Test difficulty:** 5 (panel engineering + portfolio construction).

**Results for S5**

| Date       | Universe definition | Dispersion spec | Holding / rebalance | Checklist OK? | Verdict | Notes |
| ---------- | ------------------- | --------------- | -------------------- | ------------- | ------- | ----- |
|            |                     |                 |                      |               |         |       |

---

## S6 — Slow pairs / relative value

**Idea:** On **daily** (or weekly) bars, trade **mean reversion** of a spread between liquid peers (cointegration or spread z-score). Exit on reversion, time stop, or divergence stop.

**Features (examples):**

- Spread: \(P^A - \beta P^B\) or log ratio; \(\beta\) from rolling regression or fixed prior.
- Z-score of spread vs. rolling std.

**Risks:** Corporate actions, delisting, **two-leg** costs, false cointegration in-sample.

**Test difficulty:** 6.

**Results for S6**

| Date       | Pair / universe | Beta method | Entry/exit z | Costs modeled? | Checklist OK? | Verdict | Notes |
| ---------- | --------------- | ----------- | ------------ | -------------- | ------------- | ------- | ----- |
|            |                 |             |              |                |               |         |       |

---

## S7 — Rule discovery on daily features

**Idea:** Search over **small, explicit rules** (combinations of momentum, vol, gap, regime flags) with **walk-forward** evaluation and a **complexity penalty**—not Reddit, not intraday. Hardest part is **validity**, not coding.

**Guardrails (minimum):**

- Hold out final period untouched until rule set is frozen.
- Limit number of alternative searches per quarter (lab notebook discipline).
- Prefer simpler rules that pass checklist over complex winners in-sample.

**Test difficulty:** 7 (overfitting risk dominates).

**Results for S7**

| Date       | Feature set version | Search method | Best rule (human-readable) | OOS period | Checklist OK? | Verdict | Notes |
| ---------- | ------------------- | ------------- | ---------------------------- | ---------- | ------------- | ------- | ----- |
|            |                     |               |                              |            |               |         |       |

---

## Changelog

| Date       | Change                                      |
| ---------- | ------------------------------------------- |
| 2026-03-29 | Initial list: S1–S7, constraints and tables |
