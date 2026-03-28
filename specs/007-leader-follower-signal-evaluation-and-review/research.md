# Research: Leader-Follower Signal Evaluation

**Feature**: 007-leader-follower-signal-evaluation-and-review
**Date**: 2026-03-18

## 1. Forward Return Computation (Trading Days vs Calendar Days)

**Decision**: Use trading days (sessions), not calendar days.

**Rationale**:
- `label_service` and `PriceLabel` already use trading-day logic for consistency with market data.
- `label_service.compute_and_store_forward_returns` implements: sorted dates per symbol, index-based lookup for h-th next session, `close[target]/close[D] - 1`.
- Reusing this pattern avoids drift and keeps evaluation comparable to research datasets.

**Alternatives considered**:
- Calendar days: Rejected — weekends/holidays would misalign with actual price bars.

---

## 2. Price Reference for Entry and Target

**Decision**: Close-to-close on trading days. Entry = follower close on `signal_date`; target = follower close at h-th next trading session.

**Rationale**:
- Spec recommends close-to-close, consistent with `label_service`.
- `PriceData` stores daily OHLCV; `close` is standard for daily forward returns.
- No intraday data required.

**Alternatives considered**:
- Nearest available bar: Rejected for MVP; adds complexity; close-on-date is sufficient.

---

## 3. Missing Price Data Handling

**Decision**: Return `null` for forward return when price missing; track `evaluable_count` separately from `total_signals` so callers see the gap. Do not fail silently.

**Rationale**:
- Constitution: "Explicit failures over silence"; "Missing/incomplete data → None, [], or explicit 'no data'".
- Spec: "Handle missing price data explicitly: return null/omit; do not fail silently."

**Alternatives considered**:
- Interpolate or fabricate: Rejected — violates data integrity.
- Exclude signal entirely: Partial option — we expose both total and evaluable counts.

---

## 4. Duplicate/Overlap Definition

**Decision**: Same (leader, follower) pair within a configurable window (default 5 trading days). Count how many signals are "repeat" (another signal for same pair exists within window before/after).

**Rationale**:
- Spec: "Repeated signals for same leader/follower pair within a defined window."
- Cooldown suppresses repeats; emitted signals are post-cooldown. We quantify post-hoc overlap for analysis.
- Keep minimal: simple count, no cooldown simulator.

**Alternatives considered**:
- Full cooldown attribution: Rejected — out of scope; only evaluate emitted signals.
- Cooldown-suppressed visibility: Deferred — optional for later.

---

## 5. Computed vs Persisted

**Decision**: Compute on demand for MVP.

**Rationale**:
- Spec recommendation: on-demand sufficient for tens to low hundreds of signals.
- No new tables; always consistent with current signals and price data.
- Persist later only if profiling shows need.

---

## 6. API Style and Routing

**Decision**: Extend existing `leader_follower.py` router with sub-routes under `/api/leader-follower/evaluation/`. Use same patterns: Query params, Pydantic models, `get_session` dependency.

**Rationale**:
- Brownfield: "Follow backend/app/api/leader_follower.py patterns."
- Single router keeps leader-follower surface cohesive.
- No separate evaluation router unless size demands it.
