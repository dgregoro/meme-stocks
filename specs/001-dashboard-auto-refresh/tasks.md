# Tasks: Dashboard Auto-Refresh

**Input**: Design documents from specs/001-dashboard-auto-refresh/
**Prerequisites**: plan.md, spec.md

**Organization**: Single user story (P1).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: US1 = User Story 1

## Phase 1: Setup

- [ ] T001 Add `DASHBOARD_REFRESH_INTERVAL_MS` constant to frontend config (e.g., `frontend/src/` or env; default 60000)

## Phase 2: User Story 1 - Automatic Data Refresh (P1)

**Goal**: Dashboard refreshes automatically at configurable interval; pauses when tab hidden.

**Independent Test**: Open dashboard, wait ~60s, verify data refetches; hide tab, verify no unnecessary requests.

### Implementation for User Story 1

- [ ] T002 [P] [US1] Add refresh interval constant and visibility-awareness logic in `frontend/src/pages/Dashboard.tsx` (useEffect + document.visibilityState)
- [ ] T003 [US1] Wire periodic fetch to existing data-loading logic; ensure errors surface (no silent failure)
- [ ] T004 [US1] Pause timer when `document.visibilityState === 'hidden'`; resume when `'visible'`
- [ ] T005 [US1] Add unit test for refresh/visibility behavior (mock fetch and visibility API)

## Phase 3: Polish

- [ ] T006 Run `./scripts/verify.sh` and fix any issues
- [ ] T007 Update ROADMAP.md tracking table: mark 4.1 auto-refresh complete

## Dependencies & Execution Order

- T001 before T002
- T002, T003, T004 can overlap (same file)
- T005 after T002–T004
- T006, T007 at end

## Notes

- Backend unchanged
- Use `setInterval` + `clearInterval` with visibility listener, or a custom `useRefresh` hook
- Error state: show message/banner; allow manual retry if desired
