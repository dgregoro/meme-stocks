# Data Sources

This document describes where the application gets its market data and any plan-specific limitations.

**Social / Reddit (March 2026):** The project **originated** with Reddit as a social signal. **Reddit is no longer ingested**; there is no PRAW client or live subreddit feed in the running stack. Any “mention” or social columns in analysis or exports are **legacy or research-oriented** and may be unset or zero.

---

## Alpaca Free Plan Market Data Notes

We use **Alpaca** for intraday minute-bar ingestion when the feature is enabled.

### Feed and delay

- **`iex`** = IEX exchange only (free plan). Alpaca REST API feed parameter. **`sip`** = full consolidated SIP (requires Algo Trader Plus). The REST API does not accept `delayed_sip`.
- A safety buffer (alpaca_end_time_safety_minutes) keeps the request window at now minus safety to avoid querying too-recent data.

### How we enforce it

- Ingestion uses **`iex`** (default) or **`sip`** and ends the request window at **`now - alpaca_end_time_safety_minutes`**.
- All fetches use a single helper (`compute_safe_end_time`) in the Alpaca client so no caller can accidentally pass `end=now`.

See `backend/app/config.py` for `alpaca_data_feed`, `alpaca_free_plan_mode`, `alpaca_sip_delay_minutes`, and `alpaca_end_time_safety_minutes`. The `/intraday/status` API reports the effective lag and safety settings.
