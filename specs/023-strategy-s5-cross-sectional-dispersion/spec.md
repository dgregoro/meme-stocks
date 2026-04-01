# Feature Specification: Daily strategy S5 — Cross-sectional dispersion

**Feature Branch**: `023-strategy-s5-cross-sectional-dispersion`  
**Created**: 2026-03-30  
**Status**: Spec only — **not implemented** in product CLI  
**Input**: `docs/STRATEGY_EXPLORATION.md` S5: panel-level dispersion (e.g. dispersion of daily returns across a **defined universe**) vs forward single-name or portfolio outcomes.

## Problem

S1–S4 are **single-series or pooled parallel single-name** patterns. S5 requires a **dated panel** (many symbols aligned per day) and explicit **universe rules** (constituents, liquidity, survivorship policy).

## Out of scope (until implemented)

- No `evaluate daily-strategy s5` command yet.
- Universe definition may reuse `research universe` outputs; implementation TBD in plan phase.

## Acceptance (when implemented)

- Documented universe + dispersion definition; causal labeling (no future constituents).
- CLI parity target: `s5`, `s5-merit`, `eval-bundle --strategy s5` following S4 patterns.
- Tests with synthetic multi-symbol panels.
