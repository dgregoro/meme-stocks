# Tasks: Leader-Follower Historical Backfill and Replay

**Input**: Design documents from `/specs/008-leader-follower-historical-backfill-and-replay/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [x] T001 Add `exists_for(leader, follower, signal_date)` to `LeaderFollowerSignalRepository` in `backend/app/data/repositories/leader_follower_signal_repo.py` for idempotent insert check

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T002 Add `fetch_daily_bars_for_range` or equivalent in `backend/app/clients/alpaca_data_client.py` (or replay service) that calls `fetch_bars_page` with `timeframe="1Day"`, handles paging, returns list of bar dicts per symbol
- [x] T003 Add `run_detection_for_date(db, event_date, run_id)` in `backend/app/services/leader_follower_service.py` that uses passed event_date instead of compute_event_date, reuses detect_leaders/select_follower_candidates/create_signals
- [x] T004 Add `create_signals_for_replay` variant or extend `create_signals` to accept optional idempotent check and dry-run cooldown dict; ensure create_signals skips when exists_for returns True in persist mode

---

## Phase 3: User Story 1 — Backfill Date Range (P1) MVP

**Goal**: CLI command replays detection over date range with dry-run and persist.

- [x] T005 [US1] Create `leader_follower_replay_service.py` with `backfill_price_data_from_alpaca(db, symbols, start_date, end_date)` — fetch Alpaca daily bars, map to PriceData, persist
- [x] T006 [US1] Add `run_backfill(db, start_date, end_date, dry_run, persist, replace_range)` in replay service — orchestrate backfill → per-date detection → summary
- [x] T007 [US1] Implement trading-day iteration (chronological); skip weekends/holidays when no data; collect ReplaySummary
- [x] T008 [US1] Add `backfill leader-follower` command to `backend/app/cli.py` with --start, --end, --dry-run, --replace-range

---

## Phase 4: User Story 4 — Persistence and Idempotency (P4)

**Goal**: Safe reruns; no duplicate signals.

- [x] T009 [US4] In replay service persist path: before insert, call `exists_for`; skip and increment signals_skipped_duplicate if True
- [x] T010 [US4] Add `--replace-range` support: delete existing signals in [start,end] before replay when flag set

---

## Phase 5: User Story 5 — Observability (P5)

**Goal**: Progress, warnings, failures visible.

- [x] T011 [US5] Ensure ReplaySummary includes days_processed, days_skipped, leaders_detected, candidates_found, signals_emitted, signals_skipped_duplicate, missing_data_warnings, errors
- [x] T012 [US5] Log at INFO per date; WARNING for skipped dates/missing data; ERROR for Alpaca failures; print summary to stdout

---

## Phase 6: Polish & Cross-Cutting

- [x] T013 Add unit tests for replay service in `backend/tests/test_leader_follower_replay_service.py` (mock Alpaca, test dry-run summary, test idempotency)
- [ ] T014 Add CLI integration test for `backfill leader-follower --dry-run`
- [x] T015 Run `./scripts/verify.sh` and fix any failures
- [ ] T016 Run quickstart verification from `specs/008-leader-follower-historical-backfill-and-replay/quickstart.md`

---

## Dependencies

| Phase | Depends on | Blocks |
|-------|------------|--------|
| 1 Setup | — | 2 |
| 2 Foundational | 1 | 3–5 |
| 3 US1 | 2 | — |
| 4 US4 | 2, 3 | — |
| 5 US5 | 2, 3 | — |
| 6 Polish | 3–5 | — |

## MVP Scope

Phases 1–3 deliver CLI backfill with dry-run and persist. US2 (lookahead) and US3 (evaluation compatibility) are satisfied by design.
