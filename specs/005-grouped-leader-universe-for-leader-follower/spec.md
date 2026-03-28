# Feature Specification: Grouped Leader Universe for Leader-Follower

**Feature Name**: grouped-leader-universe-for-leader-follower
**Feature Branch**: `005-grouped-leader-universe-for-leader-follower`
**Created**: 2026-03-22
**Status**: Draft
**ROADMAP**: Phase 3/4 bootstrap-phase alignment
**Input**: Restrict leader detection to `stock_groups` symbols so the leader-follower pipeline is coherent during the bootstrap phase; improve diagnostics and docs.

---

## Problem Statement

The current leader-follower implementation detects leaders from the full stock universe but generates follower candidates only from `stock_groups`. This mismatch causes many successful leader detections to produce zero follower candidates.

**Observed behavior (meme-stocks-vps, 2026-03-22):**
- Input universe: ~1601 symbols
- Leaders detected: 9 (UMAC, SLS, PLAY, MEME, GDRX, EWY, EU, ANNA, AIR)
- Follower candidates: 0
- `empty_reason`: `no_candidates`

**Root cause:** The 9 leaders are not in any curated `stock_groups` group. Follower candidate generation looks up `get_groups_for_symbol(leader_symbol)` for each leader; when the leader is not in `stock_groups`, it returns no groups and thus no candidates. The system is structurally misaligned: leader detection scans everything, follower logic only works for grouped symbols.

The system needs a coherent bootstrap-phase universe so that detected leaders can actually produce candidate followers. This is an intentional, temporary design choice to make the pipeline debuggable and evaluable until future work adds learned relationships or broader discovery.

---

## Goals

- Restrict leader detection for the leader-follower feature to grouped symbols only
- Preserve the broader stock universe for unrelated features (price collection, Reddit, analytics)
- Make diagnostics clearly show:
  - full stock universe size
  - grouped leader universe size
  - leaders detected
  - follower candidates found
  - signals emitted
- Improve the explainability of empty results with structured `empty_reason` and stage counts

---

## Non-Goals

- No learned relationship discovery
- No broadening of the grouped universe just to absorb random recent leaders
- No major architectural rewrite
- No changes to unrelated ingestion or analysis features
- No sentiment integration
- No replacement of `stock_groups` with pairwise relationships in this spec

---

## User Stories

### User Story 1: Coherent bootstrap leader detection

As a developer, I want leader-follower detection to only consider grouped symbols as eligible leaders, so that any detected leader has a plausible path to follower candidate selection.

**Acceptance criteria:**
- leader-follower leader detection uses only symbols present in `stock_groups`
- unrelated features (price collection, Reddit ingestion, daily analysis, notifications) continue to use the broader stock universe unchanged
- if `stock_groups` is non-empty, the grouped leader universe is explicitly measurable and exposed in metrics

---

### User Story 2: Inspect grouped leader universe coverage

As a developer or operator, I want diagnostics to show both the full stock universe size and the grouped leader universe size, so that I can tell whether the grouped universe is too small or empty.

**Acceptance criteria:**
- job metrics include `input_universe_size` (full stocks table)
- job metrics include `grouped_leader_universe_size` (distinct symbols in `stock_groups`)
- if grouped universe is empty, that is surfaced clearly in diagnostics (warning and/or `empty_reason`)

---

### User Story 3: Explain empty results more accurately

As a developer or operator, I want clear empty-state diagnostics, so that I can distinguish between:
- no run
- `stock_groups` empty
- grouped leader universe empty
- no leaders detected in grouped universe
- leaders found but no follower candidates found
- candidates found but no signals emitted

**Acceptance criteria:**
- empty-state responses use structured `empty_reason` (or equivalent) fields
- responses are specific enough to localize the failure stage without direct DB inspection
- existing `empty_reason` values (e.g. `no_run`, `failed`, `no_leaders`, `no_candidates`, `no_confirmations`, `ok`) are extended or refined to cover `stock_groups_empty` and `grouped_universe_empty` where appropriate

---

### User Story 4: Understand bootstrap design through docs

As a developer, I want the documentation to explain that `stock_groups` currently defines the bootstrap leader/follower universe, so that I understand why only grouped symbols can become leaders in this phase.

**Acceptance criteria:**
- docs explain current bootstrap-phase behavior
- docs explain limitations and future direction
- docs do not overclaim this as true follower discovery

---

## Functional Requirements

### 1. Grouped leader universe

- The feature must derive a distinct set of symbols from `stock_groups` (e.g. `StockGroupRepository` helper or inline distinct symbol query)
- Only those symbols are eligible for leader detection in the leader-follower pipeline
- If a symbol is not in `stock_groups`, it must not be treated as a leader for this feature
- If `stock_groups` is empty, the grouped leader universe is empty and leader detection must short-circuit (no leaders, no candidates)

### 2. Feature-local scope

- This grouped-universe restriction must apply only to the leader-follower feature
- Other jobs (price collection, Reddit collection, daily analysis, notification check, intraday ingestion) and APIs must remain unchanged unless explicitly part of this feature

### 3. Observability and metrics

- Every leader-follower run must expose in `metrics_json`:
  - `input_universe_size` (total stocks)
  - `grouped_leader_universe_size` (distinct symbols in `stock_groups`)
  - `leader_events_detected`
  - `follower_candidates_found`
  - `signals_emitted`
  - `symbols_skipped`, `errors_count` where available
- If `stock_groups` is empty, a warning must be emitted (existing startup/job warning can remain; ensure it is still accurate)
- If grouped universe is empty (e.g. after filtering for price data availability), that must be clearly surfaced in diagnostics

### 4. Diagnostics and API behavior

- Existing leader-follower diagnostics (`GET /api/leader-follower/status`, signals `diagnostics`) must be extended or clarified so they can explain why no results were produced
- The diagnostics must differentiate:
  - no run
  - `stock_groups` empty
  - grouped leader universe empty
  - no leaders found in grouped universe
  - no candidates found
  - no signals after confirmation

### 5. Documentation

- Update `docs/STOCK_GROUPS_BOOTSTRAP.md` and related docs to explain:
  - current bootstrap-phase universe restriction (leader detection scoped to grouped symbols)
  - why this is intentional
  - how `stock_groups` interacts with leader detection and follower candidate generation
  - future likely evolution toward stronger relationship modeling (learned pairs, broader discovery)

---

## Data Requirements

- **stock_groups**: Existing table and `StockGroupRepository`. Need a method (or inline logic) to get distinct symbols: `get_symbols_in_any_group()` or derive from `get_all_symbol_group_pairs()`.
- **stocks**: Existing table. Full universe for other features; grouped subset for leader-follower.
- **Existing leader-follower run metrics**: `job_run_history.metrics_json` already contains stage counts. Extend with `grouped_leader_universe_size`.
- No major new data source dependencies.

---

## Risks / Tradeoffs

| Risk | Mitigation |
|------|-------------|
| Smaller grouped universe may reduce leader count | Intentional. Signals may be sparse until grouped universe is expanded thoughtfully. This is a deliberate bias toward coherence and debuggability over market-wide coverage. |
| Users may confuse bootstrap grouping with true follower discovery | Docs must be explicit that this is a bootstrap-phase design choice; future work may add learned relationships. |
| Grouped symbols may lack price data on event_date | Existing behavior: symbols without sufficient price data are skipped. Diagnostics should make it clear when grouped universe is non-empty but no leaders are found (e.g. insufficient price data). |
| Fewer leaders could mean fewer signals | Acceptable during bootstrap. The pipeline becomes evaluable; we can add groups or expand later. |

---

## Brownfield Constraints

- Keep changes minimal
- Reuse existing repository/service patterns (`StockGroupRepository`, `LeaderEventRepository`, `run_detection`)
- Avoid large new subsystems
- Avoid broad schema churn unless truly necessary
- Prefer clear diagnostics over hidden behavior

---

## Open Questions

1. **Should grouped leader universe size be exposed in both job runs and API diagnostics?** Recommendation: Yes. Add to `metrics_json` and to `stage_counts` in status/signals diagnostics.

2. **Should there be a warning threshold when grouped universe is very small, not just empty?** Recommendation: Defer. A single warning at empty is sufficient for MVP. A "very small" threshold (e.g. &lt; 10 symbols) could be added later if operators request it.

3. **Should ungrouped detected leaders be counted anywhere for research purposes, or fully excluded in this phase?** Recommendation: Fully excluded. We are not chasing every random leader; we want a coherent bootstrap. Counting them would add complexity and could encourage scope creep. Future evaluation specs can revisit.

---

## Appendix: Current Repo Context

| Component | Path | Current Behavior |
|-----------|------|------------------|
| Leader detection | `backend/app/services/leader_follower_service.py` `detect_leaders()` | Iterates over `stock_repo.list()` (full universe) |
| Follower candidate selection | `select_follower_candidates()` | Uses `stock_group_repo.get_groups_for_symbol(leader_symbol)`; returns [] if leader not in any group |
| Stock groups | `backend/app/data/repositories/stock_group_repo.py` | Has `get_groups_for_symbol`, `get_symbols_in_group`, `get_all_symbol_group_pairs`, `list_group_ids`, `count_total` |
| Run metrics | `run_detection()` return dict | `input_universe_size`, `leader_events_detected`, `follower_candidates_found`, `signals_emitted` |
| Bootstrap seed | `backend/app/data/stock_group_seed.py`, `seed stock-groups` | Curated groups: semis, banks, oil, megacap_tech, meme |
| Status API | `GET /api/leader-follower/status` | Returns `last_run`, `stage_counts`, `empty_reason` |

---

## Recommended MVP Implementation Approach

1. **Add grouped-universe helper**
   Add `get_all_symbols()` or equivalent to `StockGroupRepository` that returns distinct symbols present in any group. Use this as the leader-eligibility set.

2. **Restrict `detect_leaders`**
   In `leader_follower_service.detect_leaders()`, replace the iteration over `stock_repo.list()` with iteration over `stock_group_repo.get_all_symbols()` (or equivalent). If the grouped set is empty, return immediately and skip leader detection.

3. **Extend `run_detection` metrics**
   Add `grouped_leader_universe_size` to the metrics dict returned by `run_detection`. Compute before leader detection; persist in `metrics_json`.

4. **Refine `empty_reason`**
   Update `_derive_empty_reason` (or equivalent logic in leader_follower API) to handle `stock_groups_empty` and `grouped_universe_empty` before `no_leaders`.

5. **Document**
   Update `docs/STOCK_GROUPS_BOOTSTRAP.md` to state that leader detection is scoped to grouped symbols during the bootstrap phase.

---

## Likely Files / Modules Affected

| File | Change |
|------|--------|
| `backend/app/services/leader_follower_service.py` | Restrict `detect_leaders` to grouped symbols; add `grouped_leader_universe_size` to `run_detection` metrics |
| `backend/app/data/repositories/stock_group_repo.py` | Add `get_all_symbols()` or equivalent (or use existing `get_all_symbol_group_pairs` and derive) |
| `backend/app/api/leader_follower.py` | Extend `stage_counts` with `grouped_leader_universe_size`; refine `empty_reason` logic |
| `docs/STOCK_GROUPS_BOOTSTRAP.md` | Document bootstrap-phase leader scoping |

---

## Top 3 Implementation Mistakes to Avoid

1. **Changing the full universe elsewhere** — Do not modify `stock_repo.list()` usage in price collection, Reddit, or other jobs. The restriction must be isolated to the leader-follower pipeline.

2. **Over-abstracting the grouped universe** — Do not introduce a new "universe service" or config-driven abstraction. Use a simple repository method or inline distinct-symbol query. Keep it close to existing patterns.

3. **Silent empty behavior** — Do not short-circuit without updating metrics or diagnostics. When grouped universe is empty, still run the pipeline (or a no-op path) and record `grouped_leader_universe_size: 0`, `leader_events_detected: 0`, with a clear `empty_reason`.

---

## Follow-up Specs

**Evaluation/reporting:** A separate spec for evaluating leader-follower performance (backtesting, precision/recall, signal quality) is recommended after this bootstrap alignment. This spec makes the pipeline coherent; evaluation can then measure it meaningfully.

**Pairwise relationship modeling:** A separate spec for learned leader-follower relationships (correlation, lag, or ML-based) is out of scope here. This spec locks in the bootstrap design; future work can replace or extend `stock_groups` with learned pairs in a later phase.
