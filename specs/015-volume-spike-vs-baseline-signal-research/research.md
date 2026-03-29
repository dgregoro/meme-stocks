# Research: 015 Volume spike vs baseline

## Baseline statistic (mean vs median)

- **Decision**: Default **median** rolling volume over W prior trading days; support **mean** via `volume_spike_research_baseline_statistic` (`median` | `mean`).
- **Rationale**: Median is more robust to occasional past spikes polluting the baseline; spec supplement recommends median; mean remains available for comparison studies.
- **Alternatives considered**: Mean-only (simpler but noisier for illiquid names).

## Forward-return anchor date

- **Decision**: Forward return from **event_date** close to close **h** trading days later — same indexing as `compute_forward_return(symbol, ref_date, h, ...)` in `leader_follower_evaluation_service` (ref bar is the event day).
- **Rationale**: Matches existing evaluation code and tests; documented in contracts; avoids extra offset logic.
- **Alternatives considered**: Anchor at **next** trading day open/close — deferred; would change comparability with leader-follower evaluation.

## Liquidity / price filters

- **Decision**: Optional **minimum event-day close** and **minimum baseline volume** (integers/floats in config, default **0** = disabled). No mandatory dollar-volume filter in MVP.
- **Rationale**: Spec lists optional guardrails; defaults preserve inclusive behavior; researchers can tighten via env.
- **Alternatives considered**: Hard exclude penny stocks — rejected for MVP default to avoid surprising empty results.

## API namespace

- **Decision**: Prefix **`/api/volume-spike`** (flat, matches spec FR-7).
- **Rationale**: Short and grep-friendly; research-only but not nested under `/api/research` to avoid mixing with causal dataset endpoints.
- **Alternatives considered**: `/api/research/volume-spike` — acceptable future alias; not implemented in v1.

## CLI command placement

- **Decision**: `python -m backend.app.cli backfill volume-spike` and `evaluate volume-spike` under existing `backfill` Typer group for symmetry with `backfill leader-follower`.
- **Rationale**: Spec US4/US5; discoverable next to other backfills.
- **Alternatives considered**: Top-level `research volume-spike` — more nesting for marginal benefit.
