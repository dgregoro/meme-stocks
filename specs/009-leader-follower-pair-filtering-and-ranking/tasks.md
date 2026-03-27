# Tasks: Leader-Follower Pair Filtering and Ranking

**Input**: Design documents from `/specs/009-leader-follower-pair-filtering-and-ranking/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [X] T001 Add config keys to `backend/app/config.py`: `leader_follower_pair_min_signal_count` (default 2), `leader_follower_pair_min_avg_return_1d` (default 0.0), `leader_follower_pair_min_win_rate_1d` (default 0.5), `enable_pair_filtering_for_signals` (default False)

---

## Phase 2: Foundational

- [X] T002 Add `filter_pairs_by_thresholds()` and `rank_pairs()` helpers in `backend/app/services/leader_follower_evaluation_service.py` that operate on `aggregate_by_pair` output; or keep logic inline in API if helpers add no value

---

## Phase 3: User Story 1 — View ranked pairs (P1) MVP

**Goal**: API returns pairs sorted by performance (avg_return_1d default).

**Independent Test**: `GET /api/leader-follower/pairs/ranked?limit=10` returns pairs sorted by 1d avg return desc.

- [X] T003 [P] [US1] Implement `GET /api/leader-follower/pairs/ranked` in `backend/app/api/leader_follower.py` — reuse `run_evaluation` + `aggregate_by_pair`, sort by `sort_by` (default avg_return_1d), `sort_order` (default desc), support `since_date`, `until_date`, `leader`, `follower`, `limit`, optional threshold overrides
- [X] T004 [US1] Add integration test for `/pairs/ranked` in `backend/tests/test_leader_follower_api.py` — verify sorted order, response shape, empty state

---

## Phase 4: User Story 2 + 3 + 5 — Filter pairs, exclude bad, transparency

**Goal**: Filtered endpoint returns only passing pairs; response includes thresholds and pass/fail context.

**Independent Test**: `GET /api/leader-follower/pairs/filtered` returns only pairs passing thresholds; response includes `total_before_filter`, `total_after_filter`, `thresholds_applied`.

- [X] T005 [US2] [US5] Implement `GET /api/leader-follower/pairs/filtered` in `backend/app/api/leader_follower.py` — filter by min_signal_count, min_avg_return_1d, min_win_rate_1d; include `total_before_filter`, `total_after_filter`, `thresholds_applied` in response; add `filter_status` to each pair (pass/fail/insufficient_data)
- [X] T006 [US2] Add integration test for `/pairs/filtered` in `backend/tests/test_leader_follower_api.py` — verify filtering, metadata, empty state
- [X] T007 [US3] Implement `GET /api/leader-follower/pairs/blacklist` in `backend/app/api/leader_follower.py` — return empty list for MVP (or config-backed list if `leader_follower_pair_blacklist` added)

---

## Phase 5: User Story 4 — Signal generation integration (optional)

**Goal**: When `enable_pair_filtering_for_signals` is true, follower candidates are filtered by allowed pairs.

- [X] T008 [US4] Add allowed-pairs check in `backend/app/services/leader_follower_service.py` — when `enable_pair_filtering_for_signals` is true, load filtered pairs from evaluation service and filter `select_follower_candidates` output to only (leader, follower) in allowed set; compute allowed set inside job, do not call HTTP API
- [X] T009 [US4] Add integration test for signal generation with pair filtering enabled in `backend/tests/test_leader_follower_api.py` or `test_leader_follower_service.py` — verify fewer signals when filtering on, same as today when off

---

## Phase 6: Polish

- [X] T010 Run `./scripts/verify.sh` and fix any failures
- [X] T011 Update `specs/007-leader-follower-signal-evaluation-and-review/contracts/evaluation-api.md` (or create reference in 009 contracts) with new endpoint summaries
- [X] T012 Run quickstart verification from `specs/009-leader-follower-pair-filtering-and-ranking/quickstart.md`

---

## Dependencies

| Phase | Depends on | Blocks |
|-------|------------|--------|
| 1 Setup | — | 2 |
| 2 Foundational | 1 | 3 |
| 3 US1 | 2 | — |
| 4 US2+3+5 | 2 | — |
| 5 US4 | 2, 4 | — |
| 6 Polish | 3–5 | — |

## MVP Scope

Phases 1–4 deliver ranked and filtered API endpoints with transparency. Phase 5 (signal integration) is optional and behind a feature flag.
