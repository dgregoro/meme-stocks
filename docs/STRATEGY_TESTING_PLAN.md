# Plan for testing daily-frequency strategies (S1–S7)

This document is the **operational test plan** for the ideas in `docs/STRATEGY_EXPLORATION.md`: order of work, shared methodology, tooling fit, and exit criteria. It does not assume Reddit or intraday data.

**Companion docs:**

- `docs/STRATEGY_EXPLORATION.md` — definitions and **result tables** (log each run there).
- `docs/STRATEGY_CONCLUSION_FRAMEWORK.md` — **how to justify** kill vs supported conclusions (pre-registration, universe, hold-out, ablations, costs).
- `docs/SIGNAL_EVALUATION_CHECKLIST.md` — **gate** before “pursue”; fail → kill or gather more data, no tuning spiral.
- `docs/CAUSAL_RESEARCH.md` — leakage-safe habits (time-based splits, as-of features); ignore Reddit-specific artifacts when applying the spirit of the rules.

---

## 1. Principles (apply to every strategy)

### 1.1 Pre-register before you peek

For each strategy, **write down** before the first full-sample result:

- Primary hypothesis (one fork; others are secondary).
- Feature definitions (windows, formulas) and **signal → position** rule (long/short/flat, holding period).
- Universe(s), date range, and **horizons** (e.g. 1d, 5d, 10d forward).
- Train / validation / hold-out calendar splits (e.g. 60% / 20% / 20% by time, or rolling walk-forward).

Changing definitions after seeing full-sample metrics invalidates the run; log such changes as a **new** run ID in `STRATEGY_EXPLORATION.md`.

### 1.2 Leakage and alignment (daily bars)

- Features on calendar date \(t\) use only data **available at or before** that day’s close (or the cutoff you adopt consistently for `open`/`close` semantics).
- Gap features (S2) that use \(O_t\): label with returns from **after** the open is known (e.g. same-day close-to-open vs. next days)—state explicitly whether the signal is knowable **at the open** vs **at the close**.
- Forward returns: use the same convention as existing price/label code (see `PriceLabel` / label services) for reproducibility.
- **Only time-based splits** for go/no-go decisions; no random shuffles of days.

### 1.3 Costs and frictions (when declaring “pursue”)

For any verdict beyond **Kill** / exploratory **Maybe**, document at least:

- Assumed round-trip cost (bps) and whether slippage is modeled.
- For S6 (pairs): two-leg execution and partial fills risk.

### 1.4 Standard output to log

For each formal run, capture in `STRATEGY_EXPLORATION.md` (global + strategy table):

- Spec hash or short config blob, sample sizes per bucket, OOS period metrics (mean/median return, win rate, concentration), and **checklist** pass/fail notes.

---

## 2. Prerequisites (once per program, not per strategy)

| Item | Purpose |
| ---- | ------- |
| **Daily OHLCV** | S1, S2, S5, S6, S7; ensure splits and adjustments policy is documented (`price_data` or export). |
| **History length** | Prefer ≥ several years for regime variety; checklist warns if &lt; ~3 months. |
| **VIX + medium-term vol** | S3; confirm series availability (e.g. VIX and VIX3M or substitute) and adjust if only VIX exists (narrower test). |
| **Calendar flags** | S4; OpEx week, FOMC week, holidays—prefer a maintained calendar table or deterministic script. |
| **Panel universe** | S5; liquid names + rules (min price, min dollar volume) and survivorship honesty. |
| **Execution environment** | Same DB / export path for backfill and evaluation (checklist §7). |

**Strategy eval preflight (CLI):** `evaluate daily-strategy` commands (`s1`, `s2`, `s1-merit`, `s2-merit`, `eval-bundle`) accept `--preflight-only` to print a JSON readiness report and exit `2` if any symbol lacks `stocks` / `price_data` for the eval window (no network). With `--ensure-data`, the CLI creates missing `stocks` rows when needed and invokes the same **Alpaca daily** backfill path as `backfill daily-prices` (requires `ALPACA_API_KEY_ID` / `ALPACA_API_SECRET_KEY`). `--ensure-data` with `--all-stocks` is capped by `daily_strategy_ensure_data_max_symbols` in config to limit accidental bulk API usage.

---

## 3. Recommended sequence (by test difficulty)

Work **S1 → S2 → S3 → S4 → S5 → S6 → S7**. Earlier IDs build habits and cheaper failures; later IDs need more engineering and stricter anti-overfitting discipline.

| Phase | Strategies | Rationale |
| ----- | ---------- | --------- |
| **A** | S1, S2 | Single-name or small universe; validate pipeline: features, labels, splits, logging. |
| **B** | S3 | Adds macro series; practice regime labeling + simple equity overlay without a large panel. |
| **C** | S4 | Easy to code, easy to fool yourself—only after A/B so splits and logging are disciplined. |
| **D** | S5 | Panel alignment and portfolio abstraction; higher implementation cost. |
| **E** | S6 | Pairs: corporate actions, two-leg costs, stability of spread. |
| **F** | S7 | Rule search last; requires frozen hold-out and complexity limits from day one. |

---

## 4. Per-strategy test procedure

### S1 — Volume vs. realized-vol mismatch

1. **Construct** rolling realized vol of daily log returns and volume z-score (pre-specify \(W_r, W_v\) and clipping).
2. **Define** discrete regimes (e.g. high/low vol × high/low volume quartiles) or a single primary flag (e.g. “high vol, low volume”).
3. **Outcome**: distribution of forward returns (1d, 5d, 10d) per regime vs. baseline; **OOS** split.
4. **Robustness**: alternate windows ±1 step; confirm sign not only at one magic pair.
5. **Gate**: `SIGNAL_EVALUATION_CHECKLIST.md`.

**Tooling fit:** Likely custom script or small service reading `price_data`; pattern similar to volume-spike / extreme-move **event** definition, but features are continuous—consider extending dataset export with these columns then reuse `experiment`-style splits if you add a thin wrapper.

---

### S2 — Gap ecology

1. **Define** gap %, vs. prior true range, and trend bucket (e.g. MA20); pre-register bucket boundaries.
2. **Clarify** tradability: signal at prior close (expected gap) vs. after open (realized gap)—pick one and stick to it.
3. **Outcome**: forward returns by bucket; minimum **N per bucket** (checklist §1).
4. **Gate**: checklist; watch multiple testing across many buckets—collapse or Bonferroni / pre-register primary bucket only.

**Tooling fit:** Pure daily OHLC; good candidate for first **reproducible** notebook or CLI that outputs CSV summary by bucket.

---

### S3 — Volatility term structure regime

1. **Ingest** daily VIX and longer-dated index (or document proxy if only VIX).
2. **Label** regimes (e.g. spread percentiles); pre-register number of regimes and thresholds **on train** only, or use fixed historical percentiles published up front.
3. **Attach** simple equity rule (e.g. SPY long-only tilt, or your baseline universe) **per regime**; evaluate **OOS** performance of rule vs. unconditional.
4. **Gate**: checklist; pay attention to **few** regime switches (sample size in each regime).

**Tooling fit:** New small join table (date → regime) + returns; not necessarily in existing Reddit dataset builder.

---

### S4 — Calendar / scheduled skeleton

1. **Pre-register** the **exact** flag set (e.g. OpEx week + FOMC week only)—no adding flags after seeing results.
2. **Primary** test: interaction with one **pre-chosen** conditioning variable (e.g. high vol quintile) if needed; avoid a grid of interactions.
3. **Outcome**: small effect sizes expected—emphasize **confidence intervals** and false-discovery risk; prefer longer history.
4. **Gate**: checklist; default verdict often **Kill** or weak **Maybe** unless evidence is unusually stable.

**Tooling fit:** Merge calendar CSV with daily returns; minimal code, maximum statistical discipline.

---

### S5 — Cross-sectional dispersion

1. **Define** universe and rebalance: daily membership vs. monthly; document delistings.
2. **Compute** \(D_t\) = cross-sectional std of daily returns across peers; signal when \(D_t\) > threshold (train-derived or fixed).
3. **Forks**: preregister **mean-reversion** vs. **momentum** portfolio rule (long short spread or long-only tilt).
4. **Outcome**: portfolio returns with realistic constraints (gross exposure, names); **OOS** walk-forward.
5. **Gate**: checklist §3 (concentration) critical here.

**Tooling fit:** Likely new panel pipeline; heaviest data engineering in this list.

---

### S6 — Slow pairs / relative value

1. **Select** 3–10 liquid pairs with economic rationale **before** mining all pairs.
2. **Estimate** \(\beta\) (rolling or static); define spread z-score and **entry/exit** (pre-registered).
3. **Corporate actions**: use adjusted prices or document failure mode.
4. **Outcome**: PnL with two-leg costs; subsample stability (different years).
5. **Gate**: checklist; fail if cointegration only in-sample.

**Tooling fit:** Pair-specific backtest script; consider weekly bars as robustness check (still daily-grade).

---

### S7 — Rule discovery on daily features

1. **Freeze** feature library (S1–S3/S4 style primitives only) and **max rule complexity** (depth, # conditions) **before** search.
2. **Search** on train only; **one** hold-out period never touched until final confirmation.
3. **Report** not only best rule but **distribution** of top-k rules (do they agree?).
4. **Gate**: checklist + explicit penalty for complexity; default **Kill** unless OOS is boringly consistent.

**Tooling fit:** `research recipe` YAML can orchestrate steps once feature export and eval commands exist; treat as **last** phase.

---

## 5. Mapping to existing repo tooling (optional acceleration)

These paths already exist; they skew Reddit/causal today but illustrate patterns:

| Area | Location / command | Use for S1–S7 |
| ---- | ------------------- | ------------- |
| CLI entrypoint | `python -m backend.app.cli --help` | Wire new subcommands or recipes as you add signals. |
| Research recipes | `python -m backend.app.cli research recipe run …` | Phase F orchestration once steps are stable. |
| Rolling robustness | `robustness` CLI (if configured for your experiment) | Walk-forward summaries after baseline event study works. |
| Evaluate summaries | `evaluate extreme-move`, `evaluate volume-spike` | Templates for “event → forward returns” reporting. |
| Daily strategy S1/S2 | `python -m backend.app.cli evaluate daily-strategy s1 --symbol SPY` (optional `--start` / `--end`) | Same forward-return machinery; regimes/buckets from daily OHLCV. Use `… daily-strategy s2 …` for gap ecology. |
| S1 merit (automated gate) | `python -m backend.app.cli evaluate daily-strategy s1-merit --start YYYY-MM-DD --end YYYY-MM-DD --symbols A,B` or `--all-stocks` | **Pooled** regimes over the window, **vs unconditional baseline** (same days), concentration + **checklist** in JSON (`daily_strategy_merit_*` in config). |
| S1 merit rolling | Same command + `--splits N` (e.g. 4) | Default **`--split-mode calendar`**: **N** contiguous **calendar** chunks. **`--split-mode trading`**: **N** equal **trading-day** blocks from the union of `price_data` dates (symbols: merit universe or `--trading-calendar-symbols CSV`). If the union is empty, falls back to calendar (see `split_mode_used` in JSON). |
| S2 merit | `… daily-strategy s2-merit` | Same flags as **s1-merit** (pooled buckets, baseline, checklist, `--splits`, `--split-mode`, `--append-jsonl`). |
| S1/S2 merit log | `--append-jsonl path` | Appends **one JSON line** per run. |
| Recipe (batch) | `python -m backend.app.cli research recipe run specs/018-hypothesis-research-recipe/examples/daily-strategy-merit.yaml` | Chains **s1-merit** + **s2-merit** with example dates (edit YAML first). |
| Extreme / volume events | `backfill` research commands | Shows how persisted **events** are built from `price_data`; S1/S2 might add new event types or separate analysis tables. |

**Gap:** None of the above implements S3–S7 end-to-end without new code or external notebooks; the plan assumes you will add minimal glue (export + evaluation script) per strategy until patterns stabilize.

---

## 6. Decision flow

```text
Pre-register spec → Build features (train period only for thresholds) →
  OOS evaluation → SIGNAL_EVALUATION_CHECKLIST →
    Kill / Maybe / Pursue → Log in STRATEGY_EXPLORATION.md
```

- **Kill:** stop; optionally archive lesson learned in strategy section “Notes.”
- **Maybe:** one narrow follow-up with **new** pre-registration; no parameter sweep hunting.
- **Pursue:** document costs, risks, and next step (paper, sizing cap, monitoring).

---

## 7. Changelog

| Date       | Change                          |
| ---------- | ------------------------------- |
| 2026-03-29 | Initial testing plan for S1–S7 |
