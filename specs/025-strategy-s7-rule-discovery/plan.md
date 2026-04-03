# Plan: S7 rule discovery (deferred)

1. Define feature matrix source (derived from OHLCV + optional macro columns).
2. Choose search algorithm scope (exhaustive small spaces vs heuristic; document bias).
3. Implement evaluation only **after** protocol is reviewed (likely separate research command namespace).
4. Do **not** add to `eval-bundle` until ROADMAP explicitly approves.

**Current state:** MVP implemented — `backend/app/services/s7_rule_discovery.py`, `research rule-discovery build-matrix` / `run-search --ack-overfitting-risk`. Still **not** in `eval-bundle` until explicitly approved.
