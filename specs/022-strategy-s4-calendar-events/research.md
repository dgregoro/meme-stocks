# Research: S4 calendar events (Phase 0)

All items resolved; no outstanding NEEDS CLARIFICATION.

## R1 — Calendar vs last trading day of month

- **Decision:** Use **calendar** month-end (`day == last day of month`) and document that the signal only fires on dates where a **price bar exists**.
- **Rationale:** Avoids dependency on exchange holiday calendars in v1; matches spec non-goals.
- **Alternatives considered:** NYSE calendar package or `pandas_market_calendars` — rejected for slice scope and extra dependency.

## R2 — OpEx week definition

- **Decision:** **Monday–Friday of the ISO week** containing the **third Friday** of the month (US monthly equity options convention); weekends excluded from `is_opex_week`.
- **Rationale:** Stable, documented, pure `datetime`.
- **Alternatives considered:** Holiday-adjusted expiry — out of scope.

## R3 — Bucket key stability under config toggles

- **Decision:** Fixed namespace `cal_abc` with bits forced to **0** when a dimension is disabled (`s4_bucket_label`), so keys stay in `cal_000`…`cal_111`.
- **Rationale:** Pooled merit and rolling rollup can use a fixed `S4_BUCKET_KEYS` tuple.
- **Alternatives considered:** Dynamic key set per config — harder to compare reports across runs.

## R4 — Baseline definition

- **Decision:** Same as S2: **all** eligible window days contribute to unconditional baseline forward returns; flagged days also contribute to **bucket** samples.
- **Rationale:** Consistent with existing daily-strategy methodology.

## R5 — Integration with persistence

- **Decision:** `kind` values `s4_merit_report` and `s4_merit_report_rolling`; `strategy_id` `s4` in bundle rows.
- **Rationale:** Mirrors `s2_*` / `s3_*` in `daily_strategy_merit_persistence.py`.
