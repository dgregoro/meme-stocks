# Tasks: 025-strategy-s7-rule-discovery

- [ ] Protocol doc: hold-out, complexity, reporting (spec + STRATEGY_CONCLUSION_FRAMEWORK link)
- [x] Feature matrix builder (deterministic, versioned) — `backend/app/services/s7_rule_discovery.py` + `research rule-discovery build-matrix`
- [x] Search runner (Typer subcommand, gated / opt-in) — `research rule-discovery run-search --ack-overfitting-risk`
- [x] Tests on toy feature CSV / synthetic labels — `backend/tests/test_s7_rule_discovery.py`
