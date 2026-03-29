# 018 — Hypothesis research recipe runner

## Goal

Let an operator **repeat multi-step research flows** (CLI chains) from a **single YAML file**, with optional `--dry-run`, so hypotheses can be tested with less copy-paste and fewer environment mistakes.

## Non-goals

- Not a new backtest engine or strategy DSL.
- Not sandboxing arbitrary shell (recipes are **trusted**; same caution as shell scripts).
- Not replacing individual CLIs—only **orchestration**.

## Requirements

1. **Recipe format** (YAML): version, optional `name`, list of `steps`; each step has optional `name` and required `argv` (list of strings passed after `python -m backend.app.cli`).
2. **CLI**: `python -m backend.app.cli research recipe run <path>` with `--dry-run` and `--cwd`.
3. **Optional**: `research recipe validate <path>` — parse and print normalized recipe JSON (no subprocess).
4. **Failures**: non-zero exit if parse fails or any step subprocess returns non-zero; structured stderr message.
5. **Tests**: parser validation, dry-run produces no subprocess, one test with mocked successful subprocess.

## Success criteria

- Example recipe under `specs/018-hypothesis-research-recipe/examples/` runs end-to-end in dev (document prerequisites).
- `./scripts/verify.sh` passes.

## References

- `docs/PURPOSE.md` — hypothesis → measurable edge or kill; recipes reduce friction on that path.
- `docs/SPEC_KIT_USAGE.md` — Spec Kit workflow.
