# Data Sources

This document describes where the application gets its market and social data, and any plan-specific limitations.

---

## Alpaca Free Plan Market Data Notes

We use **Alpaca** for intraday minute-bar ingestion when the feature is enabled.

### Feed and delay

- **`delayed_sip`** = 15-minute delayed consolidated SIP (Securities Information Processor). On the Alpaca free plan, full-market real-time is not available; the SIP feed is delayed by 15 minutes.
- **Do not query within the last 15 minutes** when using delayed SIP on the free plan—requests that ask for data too close to “now” can fail with 4xx errors.
- **Real-time on the free plan is IEX-only**, not consolidated full-market. We do not use IEX for this ingestion; we use delayed SIP for broad market coverage.

### How we enforce it

- Ingestion uses **delayed_sip** and intentionally ends the request window at **`now - alpaca_end_time_safety_minutes`** (default 20 minutes). That keeps us safely behind the 15-minute delay and allows for clock skew.
- All fetches use a single helper (`compute_safe_end_time`) in the Alpaca client so no caller can accidentally pass `end=now`.

See `backend/app/config.py` for `alpaca_data_feed`, `alpaca_free_plan_mode`, `alpaca_sip_delay_minutes`, and `alpaca_end_time_safety_minutes`. The `/intraday/status` API reports the effective lag and safety settings.
