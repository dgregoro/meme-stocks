# Implementation Plan: Dashboard Auto-Refresh

**Branch**: `001-dashboard-auto-refresh` | **Date**: 2026-03-13 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from specs/001-dashboard-auto-refresh/spec.md

## Summary

Add automatic polling to the Dashboard page with configurable interval (default 60s). Use `document.visibilityState` (or Page Visibility API) to pause refresh when the tab is hidden. Surface refresh errors visibly; no silent failures.

## Technical Context

**Language/Version**: TypeScript (React), Python 3.11 (backend unchanged)  
**Primary Dependencies**: React, Vite, existing `frontend/src/services/api.ts`  
**Storage**: N/A (stateless frontend; backend unchanged)  
**Testing**: Vitest (frontend), existing test setup  
**Target Platform**: Web browser (Chrome, Firefox, Safari)  
**Project Type**: Frontend enhancement to existing SPA  
**Constraints**: No new backend endpoints; reuse existing API.

## Constitution Check

- ✅ Roadmap alignment: Phase 4.1, NFR-6.3
- ✅ Explicit failures: Errors surfaced in UI
- ✅ Test discipline: Add tests for refresh logic
- ✅ Minimal diffs: Frontend-only change

## Project Structure

### Documentation (this feature)

```text
specs/001-dashboard-auto-refresh/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── pages/
│   │   └── Dashboard.tsx       # Add useEffect for polling + visibility
│   └── ...
```

Backend: no changes.

## Implementation Approach

1. Add a `useInterval` or `useRefresh` hook (or inline `useEffect`) that:
   - Calls the existing dashboard data fetch at the configured interval
   - Pauses when `document.visibilityState === 'hidden'`
   - Resumes when visibility returns to `'visible'`
2. Add a config constant for interval (e.g., `DASHBOARD_REFRESH_INTERVAL_MS = 60_000`)
3. Wire error handling: on fetch failure, set error state and show in UI; do not crash
4. Add unit test for the refresh/visibility logic (mock fetch, mock visibility API)

## Complexity Tracking

None. Single-file or small-scope change; no new architecture.
