# Research: Grouped Leader Universe for Leader-Follower

**Feature**: 005-grouped-leader-universe-for-leader-follower
**Date**: 2026-03-22

## 1. Grouped Universe Derivation

**Decision**: Add `get_all_symbols()` to `StockGroupRepository` that returns distinct symbols present in any group, ordered lexicographically.

**Rationale**:
- Explicit method improves readability and testability over inline derivation from `get_all_symbol_group_pairs()`.
- Matches existing repo patterns (`list_group_ids`, `get_symbols_in_group`).
- Single query: `SELECT DISTINCT stock_symbol FROM stock_groups ORDER BY stock_symbol`.
- Keeps logic in the repository layer where group data lives.

**Alternatives considered**:
- **Inline derivation**: `sorted(set(s for s, g in repo.get_all_symbol_group_pairs()))`. Rejected: less readable; pulls all pairs when only distinct symbols are needed; no clear home for the logic.
- **Service-level helper**: `leader_follower_service._get_grouped_symbols(db)`. Rejected: crosses layer boundary; repository owns group data access.

---

## 2. Empty-Reason Values

**Decision**: Extend `empty_reason` with:
- `stock_groups_empty` — `stock_groups` table has zero rows
- `grouped_universe_empty` — `stock_groups` has rows but `get_all_symbols()` returns [] (edge case; logically same as stock_groups_empty for this feature)

For practical purposes, treat both as "no grouped symbols". Use `stock_groups_empty` when `count_total() == 0`; if we ever have groups with no symbols, `grouped_universe_empty` would apply. MVP: use `stock_groups_empty` when grouped universe size is 0.

**Rationale**: Spec requires distinguishing "stock_groups empty" from "no leaders found in grouped universe". The former explains why the pipeline short-circuits before leader detection.

**Alternatives considered**:
- **Single "no_grouped_universe"**: Combines both. Rejected: spec explicitly calls out stock_groups_empty for clarity.
- **Reuse "no_leaders"**: When grouped universe is empty, we also have no leaders. Rejected: conflates cause (empty groups) with effect (no leaders). Diagnostic value is in explaining the cause.

---

## 3. Short-Circuit Behavior

**Decision**: When `get_all_symbols()` returns empty, skip the leader detection loop entirely. Still compute `event_date`, record `input_universe_size` (full stocks), `grouped_leader_universe_size: 0`, `leader_events_detected: 0`, `follower_candidates_found: 0`, `signals_emitted: 0`.

**Rationale**: Avoids unnecessary iteration; makes the "empty grouped universe" path explicit and cheap. Metrics remain consistent for diagnostics.

---

## 4. Feature Isolation

**Decision**: Only `detect_leaders` and `run_detection` in `leader_follower_service.py` use the grouped universe. No changes to:
- `StockRepository.list()` elsewhere
- Price collection (continues to collect for full universe or configured set)
- Reddit ingestion
- Notification logic
- Any other job or API

**Rationale**: Spec requires feature-local scope. Minimal blast radius.
