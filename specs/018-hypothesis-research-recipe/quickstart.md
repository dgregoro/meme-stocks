# Quickstart: research recipes (018)

## Validate a recipe (no execution)

```bash
# From repo root; PYTHONPATH must include project root (or use container /app)
python -m backend.app.cli research recipe validate \
  specs/018-hypothesis-research-recipe/examples/extreme-move-eval.yaml
```

## Dry run (print full subprocess commands)

```bash
python -m backend.app.cli research recipe run \
  specs/018-hypothesis-research-recipe/examples/extreme-move-eval.yaml \
  --dry-run
```

## Execute

Requires the same DB/env as running individual CLI commands.

```bash
python -m backend.app.cli research recipe run \
  specs/018-hypothesis-research-recipe/examples/extreme-move-eval.yaml
```

**Container:**

```bash
podman exec meme-stocks-backend python -m backend.app.cli research recipe run \
  /path/inside/container/to/recipe.yaml
```

Mount or copy the YAML into the container if needed.

## Format

See `contracts/recipe-format.md`.
