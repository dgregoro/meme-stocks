# Research: Combined Signal Alerts

**Branch**: 002-combined-signal-alerts | **Date**: 2026-03-13

## 1. Signal Aggregation Architecture

**Decision**: Add a new `combined_signal_service` that consumes outputs from existing detectors (via normalized inputs) and computes a weighted score. The notification_service flow: gather all signals → normalize via lightweight adapter if needed → aggregate → create combined notification when threshold met. Individual alerts continue by default.

**Rationale**: Spec requires no modification to detectors (FR-005). Dedicated service keeps aggregation testable. Adapter logic acceptable for heterogeneous detector outputs.

**Alternatives considered**: Modify detectors — rejected. Inline aggregation only — acceptable but less testable.

## 2. Feature Flag: Combined vs. Individual Alerts

**Decision**: Add config `combined_signal_alerts_only` (bool, default `false`).

**Default (`false`)**: Individual alerts (volume, price, sentiment) continue as today. Combined alerts are created in addition when threshold met. Both coexist.

**When `true`**: Only combined alerts are created; individual alerts are suppressed.

**Rationale**: Safe rollout. Operators preserve current behavior by default. Enables phased migration to combined-only mode after validation.

**Migration**: Runtime-only; no data migration. Operators set `true` when ready.

## 3. Weight and Threshold Storage

**Decision**: Store in `backend/app/config.py`: `combined_signal_weight_sentiment`, `combined_signal_weight_price`, `combined_signal_weight_volume`, `combined_signal_weight_rsi`, `combined_signal_threshold`, `combined_signal_alerts_only`. Environment variables for overrides.

**Rationale**: Constitution requires config-driven thresholds; no magic numbers.

## 4. Notification Metadata Storage

**Decision**: Add nullable `signal_metadata` column, type **Text**. Store JSON string via `json.dumps()`. Use explicit serialization/deserialization helpers (e.g., `serialize_signal_metadata()`, `parse_signal_metadata()`). Add tests for round-trip and invalid JSON handling.

**Rationale**: Repo pattern for JSON in DB is Text + json (see `job_run_history.metrics_json`). SQLAlchemy `JSON` type is not used consistently; Text aligns with existing conventions.

**Alternatives considered**: SQLAlchemy JSON type — repo uses Text for metrics_json; prefer consistency.

## 5. Signal Source Availability and Dependencies

**Decision**: Aggregation consumes **currently available** signals only. Missing sources contribute 0. Do NOT assume RSI or volume-confirmation (ROADMAP 2.4) are present unless implemented.

**Explicit scope**:
- Consume: activity_detector (volume, price, sentiment), pattern_analyzer RSI if present
- Out of scope: Volume-confirmed pattern logic (2.4) unless already in codebase
- Missing detector output → contribution 0; no fabrication

**Rationale**: Avoid implying unfinished roadmap work is included. Spec must be implementable with today's code.

## 6. Detector Integration: Adapter Logic

**Decision**: Acknowledge that existing signal sources are heterogeneous (ActivitySignal vs PriceTrend, different structures). Lightweight adapter logic in `combined_signal_service` or `notification_service` to normalize into a common `SignalEvaluated`-like structure is acceptable and expected. Do NOT propose a detector refactor.

**Rationale**: Honest assessment. Clean consumption without any adapter is optimistic; small adapter keeps scope minimal.

## 7. RSI Signal Integration

**Decision**: If `pattern_analyzer.analyze_price_trend` returns `PriceTrend.rsi_signal` ('overbought', 'oversold', 'neutral'), use it. If not implemented or returns None, RSI contributes 0.

**Rationale**: RSI may exist (pattern_analyzer has it); ROADMAP 2.3 says "Not Started" — treat as best-effort. Missing = 0.

## 8. Explainability: Richer Metadata

**Decision**: Metadata includes `evaluation_timestamp`, `combined_score`, `threshold`, and `signals_evaluated` (all evaluated signals, not just fired). Each evaluated signal: `signal_type`, `raw_value`, `fired`, `contribution`, optional `reason`.

**Rationale**: Supports debugging and future UI. Distinguishes "evaluated but did not fire" from "not evaluated."

## 9. Backward Compatibility

**Decision**: `signal_metadata` nullable. Existing notifications remain valid. API extends response with optional `signal_metadata`; clients may ignore. Default config preserves individual alerts.
