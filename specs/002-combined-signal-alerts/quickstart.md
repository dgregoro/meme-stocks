# Quickstart: Combined Signal Alerts

**Branch**: 002-combined-signal-alerts | **Date**: 2026-03-13

## Prerequisites

- Backend running: `uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`
- At least one stock tracked with price and Reddit data

## Config

| Setting | Default | Description |
|---------|---------|-------------|
| `combined_signal_alerts_only` | `false` | When false, individual and combined alerts coexist. When true, only combined alerts. |
| `combined_signal_weight_sentiment` | 2 | Weight for sentiment shift |
| `combined_signal_weight_price` | 2 | Weight for price movement |
| `combined_signal_weight_volume` | 1 | Weight for volume spike |
| `combined_signal_weight_rsi` | 1 | Weight for RSI signal (overbought/oversold) |
| `combined_signal_threshold` | 4 | Combined score must be >= this to create alert |

**Operator expectation**: Leave `combined_signal_alerts_only=false` to preserve current behavior. Set `true` when ready for combined-only mode.

## Validation Steps

### 1. Run Tests

```bash
pytest backend/tests/test_combined_signal_service.py -v
pytest backend/tests/test_notification_service.py -v
```

### 2. Trigger Notification Check

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/notification-check
```

### 3. List Notifications

```bash
curl http://127.0.0.1:8000/api/notifications
```

Expect combined alerts to include `signal_metadata` with `evaluation_timestamp`, `combined_score`, `threshold`, `signals_evaluated`.

### 4. Full Verification

```bash
./scripts/verify.sh
```

## Expected Behavior

**Default (`combined_signal_alerts_only=false`)**:
- Individual alerts (volume, price, sentiment) created as today
- Combined alerts created when score >= threshold
- Both coexist

**Combined-only (`combined_signal_alerts_only=true`)**:
- Only combined alerts created
- No individual alerts

**Always**:
- Per-symbol failures logged; job continues
- signal_metadata includes all signals_evaluated (fired and not fired)
