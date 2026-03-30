# Slice: Net metrics reporting conventions

**Status:** Normative for new simulators. **`daily_simple_result_to_jsonable`** follows this slice (percentage-point returns, `cost_round_trip_bps`, `cost_model`). Merit JSON remains mostly gross / descriptive until versioned net fields are added.

## Purpose

When reporting returns from simulations or pooled studies, distinguish **gross** vs **net of costs** in field names so tools and humans do not mix semantics.

## Conventions (normative for new code)

| Field pattern | Meaning |
|---------------|---------|
| `*_return_pct_gross` | Before transaction costs |
| `*_return_pct_net` | After applying documented round-trip (or sum of legs if modeled) |
| `cost_round_trip_bps` | Assumption in **basis points** for the run |
| `cost_model` | Short string: `fixed_round_trip_bps` \| `fixed_round_trip_pct` \| `none` |

**Percent space:** align with `apply_round_trip_cost` — **percentage points** on simple returns (e.g. `0.1` = ten **bps** if described as “0.1% drag”).

## Merit reports (S1/S2)

- Current merit JSON is **gross** relative to baseline (descriptive).
- If net fields are added later, **add** keys; do not repurpose existing `avg_return_pct` without a major version bump + doc.

## Leader-follower paper

- Already exposes `net_return_pct` per trade; **keep** naming; reference this slice when adding new simulators.

## Acceptance

- Any **new** simulator or API in this repo documents its cost fields in its module docstring and links here.
- `docs/ARCHITECTURE.md` points to this file under research execution.
