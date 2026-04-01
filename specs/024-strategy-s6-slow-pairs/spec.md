# Feature Specification: Daily strategy S6 — Slow pairs / relative value

**Feature Branch**: `024-strategy-s6-slow-pairs`  
**Created**: 2026-03-30  
**Status**: Spec only — **not implemented**  
**Input**: `docs/STRATEGY_EXPLORATION.md` S6: **two (or few)** daily series, cointegration / spread dynamics, **corporate-action-aware** returns where applicable.

## Problem

Pair research needs **aligned returns**, **split/dividend** policy, and often **two-leg execution** assumptions. Not covered by single-name S1–S4 machinery.

## Acceptance (when implemented)

- Explicit data alignment and CA handling documented (v1 may be “adjusted close only” with warnings).
- CLI / merit hooks consistent with research execution envelope where applicable.
- Tests on synthetic spread with known mean reversion (mocked).
