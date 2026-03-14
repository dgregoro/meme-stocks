# Research: Combined Signal Alerts

**Branch**: 002-combined-signal-alerts | **Date**: 2026-03-13

## 1. Signal Aggregation Architecture

**Decision**: Add a new `combined_signal_service` that consumes outputs from existing detectors and computes a weighted score. The notification_service flow changes from "create notification per signal" to "gather all signals → aggregate → create single notification if threshold met."

**Rationale**: Spec requires no modification to existing detectors (FR-005). A dedicated service keeps aggregation logic testable and separate from notification persistence. Follows ARCHITECTURE.md service pattern.

**Alternatives considered**:
- Modify activity_detector to return a list and aggregate inline — rejected: mixes concerns, violates FR-005.
- Add aggregation inside notification_service only — acceptable but less testable; we chose a dedicated service for clarity.

## 2. Weight and Threshold Storage

**Decision**: Store weights and threshold in `backend/app/config.py` as new settings (e.g., `combined_signal_weight_sentiment`, `combined_signal_weight_price`, `combined_signal_weight_volume`, `combined_signal_weight_rsi`, `combined_signal_threshold`). Use environment variables for overrides.

**Rationale**: Constitution requires config-driven thresholds; no magic numbers (config.py pattern already established).

**Alternatives considered**:
- Database-stored config — overkill for this feature.
- File-based config — project uses env/config.py consistently.

## 3. Notification Metadata Storage

**Decision**: Add a nullable `signal_metadata` column to the Notification model. Type: JSON (SQLite supports JSON; use `Text` with JSON serialization or SQLAlchemy `JSON` type). Structure: `{"signals_fired": [...], "combined_score": float}`.

**Rationale**: Avoids new tables; Notification already exists. Nullable preserves backward compatibility for any legacy notifications. JSON allows flexible structure for signal list.

**Alternatives considered**:
- New table `notification_signal_details` — normalized but more complexity; spec says "attach metadata to alerts".
- Store in `message` field — would lose structure; FR-004 requires structured metadata.

## 4. RSI Signal Integration

**Decision**: Use `pattern_analyzer.analyze_price_trend` to obtain `PriceTrend.rsi_signal` ('overbought', 'oversold', 'neutral'). Contribute to combined score when 'overbought' or 'oversold' (configurable weight). 'neutral' or missing RSI contributes 0.

**Rationale**: RSI already implemented in pattern_analyzer (ROADMAP 2.3). Spec allows RSI slot to contribute 0 if not implemented; we have it.

**Alternatives considered**:
- Call RSI calculation separately — duplicates logic; prefer reusing analyze_price_trend.

## 5. Backward Compatibility and Migration

**Decision**: Add `signal_metadata` as nullable column. Existing notifications remain valid (metadata null). Notification API extends response model to include optional `signal_metadata`; clients that ignore it continue to work.

**Rationale**: Constitution favors incremental delivery. Migration must be backward compatible (no data loss).

## 6. Integration Point: notification_service

**Decision**: Refactor `generate_notifications_for_stock` to:
1. Gather all signals (volume, price, sentiment from activity_detector; RSI from pattern_analyzer via price data)
2. Call `combined_signal_service.evaluate(signals)` → returns `CombinedEvaluation`
3. If `evaluation.combined_score >= threshold`, create one Notification with `type="combined_signal"`, message summarizing signals, and `signal_metadata` with structured explanation
4. Do NOT create individual notifications per signal (replaces current per-signal behavior for this flow)

**Rationale**: Single entry point for notification generation; scheduler continues to call `generate_notifications_for_stock`. The refactor centralizes the "combined vs. individual" decision in one place.

**Alternatives considered**:
- Keep both individual and combined notifications — spec says "alerts only when multiple signals align"; we replace individual alerts with combined-only for clarity. Could add a feature flag later if needed.
