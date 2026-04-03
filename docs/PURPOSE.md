# Project purpose and north star

**Status:** Authoritative intent for *why* this repo exists alongside requirements (`PRD.md`) and engineering principles (`.specify/memory/constitution.md`).

---

## North star

Build a **personal, data-driven trading research system** that turns **hypothesis** → **measurable edge (or kill)** → **disciplined execution** (manual or semi-systematic), using **AI for engineering and selective modeling**—not as a substitute for validation.

---

## What this implies

- **Data-driven** means ideas are tested against historical and forward rules (paper simulation, splits, robustness)—not judged by narrative alone.
- **Novel** is an *aspiration*; the stack supports search (signals, group dynamics, social features), not proof of alpha.
- **AI** is appropriate for development velocity, documentation, and—when ready—carefully scoped modeling (e.g. features, baselines first per `CAUSAL_RESEARCH.md`). It does not replace held-out evaluation or explicit falsification.
- **Making money** is a *personal goal* of the operator. The software provides measurement and discipline; outcomes depend on markets, sizing, costs, and adherence to process. This is **not** financial advice.

---

## Relationship to other docs

| Document | Role |
|----------|------|
| `docs/PURPOSE.md` (this file) | **North star** — intent and scope of ambition |
| `docs/PRD.md` | **Requirements** — features, reliability, MVP language |
| `docs/ROADMAP.md` | **Scheduled work** — phases and tasks |
| `.specify/memory/constitution.md` | **Engineering AS-IS** — patterns and principles |
| `docs/CAUSAL_RESEARCH.md` | **Research methodology** — leakage, lead-lag, baselines |
| `docs/PRIMARY_HYPOTHESIS.md` | **H1 (closed)** leader–follower preregistration, baseline **B1**, kill criteria + Step 7 log |
| `docs/H2_HYPOTHESIS.md` | **H2 (draft)** — next preregistered hypothesis; fill and freeze before relying on results |

If PRD language reads more “retail product” than this file, treat **PURPOSE** as the operator’s strategic intent and **PRD** as what is implemented and constrained in code—update both when they intentionally diverge or converge.

---

## Last updated

April 3, 2026
