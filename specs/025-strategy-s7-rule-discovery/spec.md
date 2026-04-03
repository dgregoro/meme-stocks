# Feature Specification: Daily strategy S7 — Rule discovery on daily features

**Feature Branch**: `025-strategy-s7-rule-discovery`
**Created**: 2026-03-30
**Status**: Implemented — `research rule-discovery` CLI (build-matrix, gated run-search)
**Input**: `docs/STRATEGY_EXPLORATION.md` S7: search over rules on a daily feature matrix with **strict hold-out**, **complexity limits**, and explicit **multiple-testing / overfitting** controls.

## Problem

Open-ended rule search has **high false discovery risk**; must not share infrastructure casually with exploratory S1–S4 without guardrails.

## Acceptance (when implemented)

- Pre-registered search space + complexity penalty + frozen hold-out protocol documented.
- Outputs suitable for `ResearchRunEnvelope` / merit checklist extension (TBD).
- No default “turn-key profit” CLI without human-reviewed spec sign-off.
