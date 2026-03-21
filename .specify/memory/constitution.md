# Meme-Stocks Constitution

<!--
Sync Impact Report (v1.0.0 initial)
- Version change: N/A → 1.0.0
- Added: All principles (brownfield adoption)
- Templates: N/A (initial creation)
- Ratification: 2026-03-13
-->

## Core Principles

### I. Roadmap Alignment

All development work MUST align with `docs/ROADMAP.md`. Identify the current phase and task before implementing. Do not add features or endpoints not in the roadmap unless ROADMAP.md is updated first. When scope is unclear, ask rather than assume.

**Rationale**: Prevents scope creep and keeps delivery predictable.

### II. Explicit Failures Over Silence

Prefer explicit failures over silent behavior. Never swallow exceptions. Log and surface meaningful errors. For external APIs (Reddit, Yahoo, etc.), handle network failures, invalid responses, and rate limiting explicitly. Return clear "no data" signals instead of fabricating defaults.

**Rationale**: Silent failures make debugging impossible and undermine trust in the system.

### III. Test Discipline

Always add or update tests when adding or changing backend logic. Target 80%+ line coverage on `backend/app`. Each new service, repository, or API endpoint MUST have at least one corresponding test. Prefer unit tests for pure logic; use integration tests for DB/API paths. Run `./scripts/verify.sh` before considering any task complete.

**Rationale**: Tests protect against regressions and document expected behavior.

### IV. Skepticism and Honest Reporting

Be skeptical; do not oversell. Verify before claiming completion. Match language to evidence: "All tests pass" only after running them. Acknowledge limitations, edge cases, and deferred work explicitly. Avoid hype language.

**Rationale**: Overselling leads to missed issues and lost trust.

### V. Reliability and Observability

Follow PRD §5.0 Reliability Principles. Use structured API errors (PRD Appendix C); never expose raw stack traces. Log at error/warning levels for external API and job failures. Include correlation context (provider, endpoint, status) when possible. Background jobs must not crash the app on external failure.

**Rationale**: Production systems must degrade gracefully and remain debuggable.

### VI. Transparent Assumptions and No Look-Ahead Bias

Preserve explainability for trading and research signals. Document assumptions explicitly. In any predictive or causal work, avoid look-ahead bias and data leakage. Enforce time alignment; never use future information in training or evaluation. Label results as "lead-lag evidence," not proven causality.

**Rationale**: Financial and research claims require methodological rigor to be actionable.

### VII. Incremental Delivery and Minimal Diffs

Keep changes focused and production-minded. Prefer minimal diffs; touch the fewest files possible. Do not refactor unrelated code. Use logical, separate commits. Allowed without ROADMAP update: refactors for testability, reliability/observability improvements, small scaffolding for planned items.

**Rationale**: Small, reviewable changes reduce risk and speed iteration.

## Additional Constraints

### External API and Configuration

All external API calls MUST go through `backend/app/clients/`. Use `backend/app/utils/retry.py` for retries. Thresholds (sentiment, volume, price) MUST be in `backend/app/config.py`; no magic numbers. No hardcoded API keys or secrets.

### Architecture Patterns

Follow `docs/ARCHITECTURE.md`. Create in order: Model → Repository → Service → API Route → Tests. Keep business logic in services, not in API routes. Return dataclasses from services, not ORM models.

## Development Workflow

Before planning or implementing:

1. Read `docs/ROADMAP.md` (current phase and task)
2. Read `docs/PRD.md` §5.0 and Appendix C
3. Read `docs/ARCHITECTURE.md` for patterns

For Spec Kit workflows: Specs complement existing docs. The constitution and `.cursorrules` both apply; no conflicts. When using `/speckit.*` commands, also respect `.cursor/rules/` and `.cursorrules`.

## Governance

- This constitution supersedes ad-hoc guidance for conflicting cases.
- Amendments require a version bump and clear changelog.
- Versioning: PATCH (clarifications), MINOR (new principles), MAJOR (backward-incompatible changes).
- All PRs and agent work must verify compliance with these principles.
- Use `docs/BROWNFIELD_SPEC_KIT.md` for Spec Kit usage in this repo.

**Version**: 1.0.0 | **Ratified**: 2026-03-13 | **Last Amended**: 2026-03-13
