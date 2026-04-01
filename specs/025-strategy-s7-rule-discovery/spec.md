# Feature Specification: Daily strategy S7 — Rule discovery on daily features

**Feature Branch**: `025-strategy-s7-rule-discovery`
**Created**: 2026-03-30
**Status**: Implemented (bounded MVP) — `research rule-discovery build-matrix` + `run-search --ack-overfitting-risk`; **not** wired to `eval-bundle`
**Input**: `docs/STRATEGY_EXPLORATION.md` S7: search over rules on a daily feature matrix with **strict hold-out**, **complexity limits**, and explicit **multiple-testing / overfitting** controls.

## Problem

Open-ended rule search has **high false discovery risk**; must not share infrastructure casually with exploratory S1–S6 without guardrails.

## User stories

### P1 — Feature matrix export

**Goal**: Deterministic CSV of daily features + forward return label for one symbol.
**Independent test**: Build matrix on synthetic `price_data`; columns present; forward label aligns with close index.

### P2 — Bounded grid search

**Goal**: Single train/test split by date; quantile thresholds fit on train only; test metrics for pre-registered single-condition rules.
**Independent test**: Toy CSV where a rule has higher mean label on test when split is correct; without `--ack-overfitting-risk` CLI exits error.

### P3 — Audit envelope

**Goal**: JSON output includes `ResearchRunEnvelope` and explicit warnings.
**Independent test**: Parse output dict keys stable for downstream tools.

## Acceptance (when implemented)

- Pre-registered search space + complexity penalty + frozen hold-out protocol documented (see `research.md`, `plan.md`).
- Outputs suitable for `ResearchRunEnvelope` / merit checklist extension (TBD).
- No default “turn-key profit” CLI without human-reviewed spec sign-off — enforced by `--ack-overfitting-risk` on `run-search`.
- **Not** wired to `eval-bundle` until ROADMAP explicitly approves.
