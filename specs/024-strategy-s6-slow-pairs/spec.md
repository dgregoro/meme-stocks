# Feature Specification: Daily strategy S6 — Slow pairs / relative value

**Feature Branch**: `024-strategy-s6-slow-pairs`
**Created**: 2026-03-30
**Status**: Spec / scaffold only — **not implemented** in product CLI
**Input**: `docs/STRATEGY_EXPLORATION.md` S6: mean reversion of a spread between liquid peers (rolling beta, spread z-score); two-leg execution and corporate-action awareness.

## Problem

S1–S5 are **single-name or panel** patterns. S6 is **two-(few-)leg**: spread construction, stationarity / z-entry, and explicit **costs + divergence** handling. Implementation must not pretend splits/dividends are free.

## Out of scope (initial slice)

- Intraday execution or partial fills.
- Full survivorship-bias-free ETF pair universes (may start with explicit CLI `--leg-a` / `--leg-b`).

## Acceptance (when implemented)

- Documented spread definition (price vs log, beta estimation window, min history).
- Causal labeling: beta and z-score use data **strictly before** signal day where applicable.
- CLI parity target: `s6`, `s6-merit`, `eval-bundle --strategy s6` following S5 patterns (pair universe contract TBD).
- Tests: synthetic two-name series; no network.
