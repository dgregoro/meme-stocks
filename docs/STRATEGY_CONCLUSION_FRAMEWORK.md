# Framework for a well-supported strategy conclusion

This doc ties **`docs/PURPOSE.md`** (measure edge or kill), **`docs/SIGNAL_EVALUATION_CHECKLIST.md`**, and the **merit CLI** into a repeatable way to **justify a conclusion**—without claiming more than the evidence allows.

**Related:** `docs/STRATEGY_TESTING_PLAN.md`, `docs/STRATEGY_EXPLORATION.md`, `docs/CAUSAL_RESEARCH.md` (leakage / baselines).

---

## 1. Define the conclusion you allow yourself to state

Use one of these labels; do not upgrade without meeting the criteria in §4–§6.

| Label | Meaning |
| ----- | ------- |
| **Kill** | Hypothesis fails gates; do not trade; archive lesson. |
| **Exploratory / weak** | Interesting in-sample or thin data; **no** capital or “edge” language. |
| **Conditionally supported** | Passes checklist + hold-out + universe stress; edge **small** and **hypothesis-specific**; costs not fully modeled. |
| **Supported for paper / next stage** | Same as above + explicit cost/slippage assumption **does not** eliminate excess; you will monitor and re-evaluate on schedule. |

Nothing here is “proof of alpha”; markets change and historical patterns decay.

---

## 2. Pre-register (before you look at hold-out results)

Write down **once**, in `STRATEGY_EXPLORATION.md` or a dated note:

- **Strategy ID** (e.g. S1), **universe rule** (how symbols enter/leave), **date range** for **train/hold-out split** (or “rolling only” + number of splits).
- **Primary claim** (one sentence): e.g. “In regime `hv_lv`, average forward excess vs same-day unconditional baseline is positive at horizon 5 over held-out years.”
- **Parameters** frozen from config (`daily_strategy_*`, `daily_strategy_merit_*`)—no tuning hold-out to maximize a metric.

If you change the claim or parameters after seeing hold-out metrics, the run is a **new hypothesis**—log it separately.

---

## 3. Data and universe (avoid one-stock stories)

Minimum ambition for a **conditionally supported** conclusion:

- **Many symbols** with clean daily `price_data` (order of **tens+** for diversification; **`--all-stocks`** after backfill is closer to checklist spirit than 3 names).
- **Long calendar span** so sub-periods include different regimes (bull/bear/choppy).
- **Document** adjustments (splits), delistings, and survivorship honesty for your universe.

**Merit CLI** concentration checks matter only when **multiple symbols** contribute; with tiny universes, read **per-symbol contributions** in the JSON (pooling hides dominance).

### 3.1 How large can the universe be in *this* repo?

- **`evaluate daily-strategy … --all-stocks`** uses every row in the **`stocks`** table. Today, `python -m backend.app.cli seed stocks` fills `stocks` from **`BOOTSTRAP_GROUPS`** only (on the order of **tens** of names), not the full US listing.
- A much larger list can live in **`symbol_universe`** (e.g. refresh via the symbol-universe API in `backend/app/api/symbol_universe.py`), but **`price_data` still needs a matching `Stock` row** (FK). Growing the research universe means **creating `Stock` rows + backfilling** for each symbol you care about—subject to **storage, runtime, and your data provider’s rate limits**.
- **Reasonable “big enough” targets** for *your* setup: (a) **all bootstrap names** first; (b) then add **liquid US equities** you can actually backfill (e.g. S&P 500 constituents if you import that list into `stocks`, or a **NYSE/Nasdaq liquid subset**—many users cap at **500–3,000** names for daily research before costs dominate setup time).

### 3.2 Hold-out dates when you have no strong prior

Pick **one** primary policy and record it. Any choice is partly arbitrary; consistency beats optimizing the window after seeing results.

| Policy | When to use | Example (illustrative) |
| ------ | ----------- | ---------------------- |
| **A. Recent block hold-out** | You want a clean “future-ish” segment and enough history before it for feature/regime history. | If your last full daily bar is **2025-12-31**, use **hold-out `2024-01-01`–`2025-12-31`** (2y) and treat **2015–2023** as history for earlier bars (extend backfill as far as Alpaca/you allow). |
| **B. Last 20% trading days** | You want data-driven proportionality without naming years. | Sort trading days in your union; evaluate only the **top 20%** by time as hold-out; document the resulting calendar dates. |
| **C. Rolling only (no single hold-out)** | You dislike picking one slice; **`s1-merit --splits 5 --split-mode trading`** already stresses multiple sub-windows. | Treat **`rollup.rolling_pass`** as **time-stability** evidence; still **pre-register** the **parent** `[start,end]` and split count. |

**Avoid:** setting hold-out to the **only** period where the signal looked good in an earlier exploratory pass (that is re-optimization).

**Default suggestion if you want a single concrete answer:** use **policy A** with **last 18–24 calendar months** as hold-out and ensure you have **≥ 8–10 years** of prior data where possible for regime/vol history—then run **policy C** on the same `[start,end]` as a second line of evidence.

---

## 4. Analyses to run (automated + interpretation)

Run in order; record commands and JSON/JSONL paths.

1. **Single-window merit** — `evaluate daily-strategy s1-merit` (or `s2-merit`) on a **pre-defined evaluation window** (ideally **hold-out**).
2. **Rolling merit** — same with **`--splits` ≥ 4** and **`--split-mode trading`** for time stability closer to checklist §2. Require `rollup.rolling_pass` **and** you understand **why** any split failed (data? regime scarcity?).
3. **Ablation (falsification)** — at least one of:
   - **Different horizon** (e.g. focus was 5d—show 1d/10d do not wildly contradict the story).
   - **_shuffle / placebo (conceptual)_** — e.g. different regime label randomization is not in repo; instead: **reverse or neutral bucket** should not show the same “edge” if labels are meaningful (document what you did).
   - **Subset stress** — exclude top-N PnL symbols and see if sign of excess **survives**.

4. **Costs (manual but mandatory for “Supported for paper”)** — subtract a **round-trip bps** you believe in from **average** returns; if edge goes to ~0 or negative, downgrade to **Exploratory** or **Kill**.

5. **Benchmark narrative (optional upgrade)** — merit’s baseline is **same-symbol unconditional** same days, not SPY. For “market-neutral” language, you must **compare to SPY (or sector ETF) forward returns on the same dates** in a separate analysis; the current CLI does not replace that judgment.

---

## 5. Map evidence to `SIGNAL_EVALUATION_CHECKLIST.md`

For each section, **cite numbers** from the merit JSON (counts, medians, win rates, failures).

| Checklist section | What to show |
| ----------------- | ------------ |
| §1 Sample size | Pooled `evaluable_count` per regime/bucket ≥ thresholds; not one horizon only. |
| §2 Time stability | Rolling splits + `rollup`; note any `instability_failures`. |
| §3 Concentration | Large universe; describe **leave-one-symbol-out** or top-driver check if automated concentration is weak. |
| §4 Median vs average | Merit already flags disagreement; reconcile or kill. |
| §5 Horizon | Multiple horizons coherent, not a single magic `h`. |
| §6 Tradeability | Enough events, not ultra-clustered in time; turnover story plausible. |
| §7 Data integrity | Same DB, backfill dates, no silent gaps. |

If any **fail** after honest fixes, conclusion is **Kill** or **Exploratory** only (checklist decision rule).

---

## 6. One-page conclusion template (paste into `STRATEGY_EXPLORATION.md` or a memo)

```text
Date:
Strategy:
Pre-registration link / commit:

Claim (one sentence):
Universe (rule + N symbols + date span):
Hold-out / split policy:

Results summary:
- Single-window merit: checklist pass? (Y/N) key metrics:
- Rolling merit: rolling_pass? (Y/N) split_mode_used:
- Ablation / stress: (what you ran, outcome)

Costs: assumed round-trip ___ bps; conclusion after costs:

Limitations (honest):
- What we did not test (e.g. SPY-adjusted, live slippage, shorting)
- What would flip the conclusion

Final label: Kill | Exploratory | Conditionally supported | Supported for paper
```

---

## 7. What “well-supported” does **not** mean

- Beating backtests in one cherry-picked window.
- Passing only automated gates on **3 symbols** without stress tests.
- Ignoring **transaction costs**, **capacity**, or **regime change**.

If you want the codebase to automate more of §4 (e.g. **SPY-matched excess**, **cost subtraction**, **leave-one-out** in JSON), say which item matters most—the merit reports are intentionally conservative and incremental.

---

## Changelog

| Date | Change |
| ---- | ------ |
| 2026-03-29 | Initial framework |
