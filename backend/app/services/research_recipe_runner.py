"""Load and run YAML research recipes that chain `python -m backend.app.cli` steps (018)."""

from __future__ import annotations

import logging
import os
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

CLI_MODULE = "backend.app.cli"


class RecipeStep(BaseModel):
    """One subprocess invocation: argv tail after `python -m backend.app.cli`."""

    name: str | None = None
    argv: list[str] = Field(..., min_length=1)

    @field_validator("argv")
    @classmethod
    def argv_no_interpreter_injection(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("argv must be non-empty")
        head = v[0].strip().lower()
        if head in ("python", "python3", "uv", "sh", "bash") or head.startswith("/"):
            raise ValueError(
                "argv must start with a Typer subcommand (e.g. backfill), not an interpreter path"
            )
        if v[0] == "-m":
            raise ValueError("do not pass -m; the runner adds python -m backend.app.cli")
        return v


class ResearchRecipe(BaseModel):
    """Validated recipe v1."""

    version: int = Field(..., ge=1, le=1)
    name: str | None = None
    steps: list[RecipeStep] = Field(..., min_length=1)


def parse_recipe_yaml(text: str) -> ResearchRecipe:
    raw = yaml.safe_load(text)
    if raw is None or not isinstance(raw, dict):
        raise ValueError("recipe must be a YAML mapping")
    return ResearchRecipe.model_validate(raw)


def load_recipe_file(path: Path) -> ResearchRecipe:
    if not path.is_file():
        raise ValueError(f"recipe file not found: {path}")
    text = path.read_text(encoding="utf-8")
    return parse_recipe_yaml(text)


def run_recipe(
    recipe: ResearchRecipe,
    *,
    dry_run: bool = False,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Execute each step's argv via subprocess, or record dry-run only."""
    work = cwd if cwd is not None else Path.cwd()
    step_summaries: list[dict[str, Any]] = []

    for i, step in enumerate(recipe.steps):
        cmd = [sys.executable, "-m", CLI_MODULE, *step.argv]
        label = step.name or f"step_{i}"
        if dry_run:
            step_summaries.append(
                {
                    "index": i,
                    "name": label,
                    "dry_run": True,
                    "command": cmd,
                }
            )
            continue

        logger.info("research recipe step %s: %s", i, " ".join(cmd))
        try:
            proc = subprocess.run(  # nosec B603
                cmd,
                cwd=work,
                env=os.environ.copy(),
                check=False,
                text=True,
            )
        except OSError as e:
            raise RuntimeError(f"step {i} ({label}) failed to start subprocess: {e}") from e

        step_summaries.append(
            {
                "index": i,
                "name": label,
                "returncode": proc.returncode,
                "command": cmd,
            }
        )

        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd)

    return {
        "recipe_name": recipe.name,
        "version": recipe.version,
        "dry_run": dry_run,
        "cwd": str(work.resolve()),
        "steps": step_summaries,
    }


def run_recipe_file(path: Path, *, dry_run: bool = False, cwd: Path | None = None) -> dict[str, Any]:
    recipe = load_recipe_file(path)
    return run_recipe(recipe, dry_run=dry_run, cwd=cwd)


def recipe_to_jsonable(recipe: ResearchRecipe) -> dict[str, Any]:
    return recipe.model_dump(mode="json")
