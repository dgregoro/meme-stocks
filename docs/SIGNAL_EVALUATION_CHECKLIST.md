# Signal evaluation checklist (minimum data quality bar)

Use this checklist **before continuing work on any new signal**.
If it fails, stop or treat results as exploratory only.

---

## 1. Sample size (events)

- [ ] Total events ≥ 100
- [ ] Preferably ≥ 200 for stronger confidence
- [ ] Each event type (if applicable) ≥ 50

**Fail if:**

- fewer than 50 events total
- One event type dominates with very few others

---

## 2. Time stability (splits)

- [ ] Tested across ≥ 2 subranges (e.g. first half vs second half)
- [ ] Preferably ≥ 4–5 rolling splits
- [ ] Signal direction is consistent (no sign flip)

**Fail if:**

- Positive in one period, negative in another
- Results depend on a single window

---

## 3. Concentration (symbols / dates)

- [ ] No single symbol dominates results
- [ ] Top 5 symbols do not drive majority of returns
- [ ] Events distributed across many symbols and dates

**Fail if:**

- Results driven by meme / anomaly stocks (e.g. GME-like clusters)
- Removing a few symbols changes conclusions

---

## 4. Median vs average (outlier check)

- [ ] Median return aligns with average (same sign)
- [ ] Win rate supports the direction (above 50% for a long edge)

**Fail if:**

- Average positive but median ~0 or negative
- A few outliers explain most gains

---

## 5. Horizon consistency

- [ ] Signal works across multiple horizons (e.g. 1d, 3d, 5d)
- [ ] No single horizon carries the entire result

**Fail if:**

- Only one horizon looks good
- Longer horizons collapse or reverse

---

## 6. Realistic tradeability

- [ ] Sufficient number of events to matter in practice
- [ ] Not too sparse or too clustered
- [ ] Reasonable turnover (not dependent on rare events)

**Fail if:**

- Too few opportunities
- Requires perfect timing of rare spikes

---

## 7. Data integrity check

- [ ] Data spans meaningful time (not just a few weeks)
- [ ] No obvious gaps or anomalies
- [ ] Same DB used for backfill and evaluation

**Fail if:**

- Short history (under 3 months)
- Empty or partial datasets
- Environment mismatch (wrong DB)

---

## Decision rule

Proceed only if:

- [ ] Sample size is sufficient
- [ ] No sign flip across time
- [ ] Not concentrated in a few symbols
- [ ] Median supports the result

If any of the above fail:

1. **Do not** optimize, filter, or add ML.
2. Either gather more data or abandon the signal.

---

## Notes

- Passing this checklist does **not** mean the signal is tradable.
- Failing this checklist means the signal is **not worth further effort yet**.
- This is a **minimum bar**, not a guarantee of success.
