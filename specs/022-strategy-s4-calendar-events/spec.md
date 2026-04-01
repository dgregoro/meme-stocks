# Feature Specification: Daily strategy S4 — Calendar / scheduled-event flags

**Feature Branch**: `022-strategy-s4-calendar-events`
**Created**: 2026-03-30
**Status**: Implemented (core parity with S1–S3 CLI)
**Input**: **S4** from `docs/STRATEGY_EXPLORATION.md`: pre-registered **calendar** flags (no exchange holiday calendar) vs **forward equity returns**, with the same operational shell as S2 (baseline, pooled merit, checklist, rolling stability, preflight, persistence).

## Summary

- **Flags (config-toggleable):** third-Friday **OpEx week** (weekdays only), **calendar month-end**, **calendar quarter-end** (subset of month-ends).
- **Buckets:** stable keys `cal_abc` (`a`=OpEx, `b`=month-end, `c`=quarter-end); disabled dimensions contribute `0` in the label (`s4_bucket_label`).
- **Signal day:** any trading bar whose **calendar date** matches the union of enabled flags; forward returns from **that day’s close** (same machinery as S1–S3).
- **CLI:** `evaluate daily-strategy s4`, `s4-merit`, `eval-bundle --strategy s4` (mirrors S2/S3 flags: splits, split-mode, append-jsonl, preflight, ensure-data).

## Non-goals (this slice)

- **FOMC / macro event calendar** (no new ingest); extend via future spec if needed.
- **Last trading day of month** (requires exchange calendar); current definition is **calendar** month-end only, documented in code.

## Acceptance

1. Unit tests cover pure calendar helpers and S4 eval / merit / bundle paths with synthetic `price_data`.
2. Merit reports persist with `kind` `s4_merit_report` / `s4_merit_report_rolling` when persistence is enabled.
3. All S4 dimensions may be disabled via config → explicit failure (checklist / assessment), not silent empty success.
