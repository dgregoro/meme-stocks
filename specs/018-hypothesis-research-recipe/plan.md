# Plan: 018 — Hypothesis research recipe runner

## Approach

1. Add **PyYAML** dependency; load recipe with `yaml.safe_load`.
2. **Pydantic** models (or dataclasses) for `Recipe` / `RecipeStep` validation: `version == 1`, `steps` non-empty, each `argv` non-empty; reject `argv` if first token looks like `python` / `-m` (must be subcommand only).
3. **`research_recipe_runner` service**: `parse_recipe(path)`, `run_recipe(recipe, *, dry_run, cwd)` returning summary dict; subprocess `[sys.executable, "-m", "backend.app.cli", *argv]`.
4. **CLI** typer group `research recipe` with `run` and `validate`.
5. **Tests**: unit + subprocess mock.
6. **Docs**: example YAML, `docs/GETTING_STARTED.md` or playbook pointer (optional one line).

## Files

| File | Action |
|------|--------|
| `backend/requirements.txt` | Add `PyYAML` |
| `backend/app/services/research_recipe_runner.py` | New |
| `backend/app/cli.py` | Register `research` / `recipe` |
| `backend/tests/test_research_recipe_runner.py` | New |
| `specs/018-hypothesis-research-recipe/examples/*.yaml` | Example |

## Risks

- **Working directory**: user must run from repo root or set `PYTHONPATH` / `--cwd` consistently; document in example.
- **Container**: `podman exec ... python -m backend.app.cli research recipe run /app/recipes/x.yaml` may need recipe mounted or copied.
