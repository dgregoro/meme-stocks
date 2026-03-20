# Research: Leader-Follower Signal Detection

**Phase 0** — Design decisions resolved via spec clarifications and plan.

## 1. Leader Qualification Criteria

**Decision**: A stock qualifies as a leader only when it meets **BOTH** conditions: (a) absolute return % ≥ threshold, AND (b) volume ratio (vs rolling average) ≥ threshold.

**Rationale**: Reduces false positives from low-volume spikes or noise. Aligns with existing `activity_detector` philosophy (volume confirmation).

**Alternatives considered**: Either condition alone (rejected: too noisy); configurable AND/OR (deferred: MVP uses AND).

---

## 2. Relationship Mapping Storage

**Decision**: **DB table only** — New `stock_groups` table (group_id, stock_symbol FK). No JSON blob in config for group membership in MVP.

**Rationale**: User chose DB for inspectability, CRUD potential, and scalability. Config JSON would bloat env for large mappings.

**Alternatives considered**: Config JSON (rejected per clarification); Config + DB hybrid (deferred).

---

## 3. Strength Score Formula

**Decision**: `strength_score = w_r * norm(|return_pct|) + w_v * norm(volume_ratio)` with configurable weights in `config.py`. Normalize each metric to [0, 1] using fixed caps; clamp result to [0, 1]. Weights sum to 1.0.

**Rationale**: Captures both dimensions; interpretable; configurable for tuning.

**Alternatives considered**: Return-only (rejected: ignores volume); binary 1.0 (rejected: no ranking).

---

## 4. Reference Date (event_date) for Run

**Decision**: **Single as-of date** — `event_date = max(price_data.date)` among rows for tracked symbols in scope. All leader/follower metrics for that run use this one date.

**Rationale**: Deterministic; handles weekends; avoids mixing different "latest bar" dates per symbol. Symbols without `event_date` row are skipped with log.

**Alternatives considered**: Per-symbol latest (rejected: inconsistent); T-1 trading day (deferred: requires market calendar).

---

## 5. Cooldown for Deduplication

**Decision**: **MVP default = 1 calendar day**. Config key `leader_follower_cooldown_days` (int, default 1). Do not emit new signal for (leader, follower) if one exists with `signal_date` within cooldown window.

**Rationale**: User chose strict deduplication; 1 day avoids repeated signals from same leader move in daily batch.

**Alternatives considered**: 3 days (rejected per clarification); 5 days (rejected).

---

## 6. Primary Group When Symbol in Multiple Groups

**Decision**: Use **lexicographically smallest `group_id`** among rows containing that symbol. Deterministic; document in code and tests.

**Rationale**: Spec clarification; avoids arbitrary choice; testable.
