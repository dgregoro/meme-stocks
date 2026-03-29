# Research recipe file format (v1)

## Top-level fields

| Field | Type | Required | Notes |
|-------|------|----------|--------|
| `version` | int | yes | Must be `1` |
| `name` | string | no | Descriptive label |
| `steps` | list | yes | Non-empty |

## Step object

| Field | Type | Required | Notes |
|-------|------|----------|--------|
| `name` | string | no | Shown in logs / dry-run |
| `argv` | list[string] | yes | Arguments after `python -m backend.app.cli` (Typer subcommands and options). Example: `["backfill", "extreme-move", "--start", "2025-02-01", "--end", "2026-03-20", "--replace-range"]` |

## Security

Recipes execute subprocesses with the current interpreter. **Only run trusted recipes** (same as running a shell script).

## Example

See `specs/018-hypothesis-research-recipe/examples/extreme-move-eval.yaml`.
