# Quickstart: Combined Signal Alerts

**Branch**: 002-combined-signal-alerts | **Date**: 2026-03-13

## Prerequisites

- Backend running: `uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`
- At least one stock tracked with price and Reddit data

## Validation Steps

### 1. Run Tests

```bash
pytest backend/tests/test_combined_signal_service.py -v
pytest backend/tests/test_notification_service.py -v
```

### 2. Verify Config

Check that config includes new settings:

```bash
# In backend/app/config.py or via env
COMBINED_SIGNAL_WEIGHT_SENTIMENT=2
COMBINED_SIGNAL_WEIGHT_PRICE=2
COMBINED_SIGNAL_WEIGHT_VOLUME=1
COMBINED_SIGNAL_WEIGHT_RSI=1
COMBINED_SIGNAL_THRESHOLD=4
```

### 3. Trigger Notification Check

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/notification-check
```

### 4. List Notifications

```bash
curl http://127.0.0.1:8000/api/notifications
```

Expect notifications with `type: "combined_signal"` to include `signal_metadata` with `signals_fired` and `combined_score`.

### 5. Full Verification

```bash
./scripts/verify.sh
```

## Expected Behavior

- Single-signal events (e.g., volume spike alone) do NOT generate notifications
- Multiple signals aligning (e.g., sentiment + volume + price) generate one notification with structured metadata
- Per-symbol failures are logged; job continues for other symbols
- API response includes `signal_metadata` when type is `combined_signal`
