"""Tests for YAML research recipe loader and runner (018)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from backend.app.services.research_recipe_runner import (
    RecipeStep,
    ResearchRecipe,
    load_recipe_file,
    parse_recipe_yaml,
    run_recipe,
)


@pytest.mark.unit
def test_parse_recipe_minimal() -> None:
    text = """
version: 1
steps:
  - argv: [evaluate, extreme-move, --limit, "10"]
"""
    r = parse_recipe_yaml(text)
    assert r.version == 1
    assert len(r.steps) == 1
    assert r.steps[0].argv[:2] == ["evaluate", "extreme-move"]


@pytest.mark.unit
def test_parse_rejects_bad_version() -> None:
    text = """
version: 2
steps:
  - argv: [seed, stocks]
"""
    with pytest.raises(ValidationError):
        parse_recipe_yaml(text)


@pytest.mark.unit
def test_parse_rejects_empty_steps() -> None:
    text = """
version: 1
steps: []
"""
    with pytest.raises(ValidationError):
        parse_recipe_yaml(text)


@pytest.mark.unit
def test_parse_rejects_python_as_first_argv() -> None:
    text = """
version: 1
steps:
  - argv: [python, -m, backend.app.cli, seed, stocks]
"""
    with pytest.raises(ValidationError):
        parse_recipe_yaml(text)


@pytest.mark.unit
def test_run_recipe_dry_run_no_subprocess() -> None:
    recipe = ResearchRecipe(version=1, steps=[RecipeStep(name="a", argv=["seed", "stocks"])])
    with patch("backend.app.services.research_recipe_runner.subprocess.run") as mock_run:
        out = run_recipe(recipe, dry_run=True)
    mock_run.assert_not_called()
    assert out["dry_run"] is True
    assert len(out["steps"]) == 1
    cmd = out["steps"][0]["command"]
    assert "-m" in cmd
    assert "backend.app.cli" in cmd


@pytest.mark.unit
def test_run_recipe_executes_subprocesses() -> None:
    recipe = ResearchRecipe(version=1, steps=[RecipeStep(argv=["help"])])
    with patch("backend.app.services.research_recipe_runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        out = run_recipe(recipe, dry_run=False)
    assert mock_run.call_count == 1
    assert out["steps"][0]["returncode"] == 0


@pytest.mark.unit
def test_run_recipe_stops_on_failure() -> None:
    import subprocess

    recipe = ResearchRecipe(
        version=1,
        steps=[
            RecipeStep(argv=["help"]),
            RecipeStep(argv=["help"]),
        ],
    )
    with patch("backend.app.services.research_recipe_runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        with pytest.raises(subprocess.CalledProcessError):
            run_recipe(recipe, dry_run=False)
    assert mock_run.call_count == 1


@pytest.mark.integration
def test_load_example_recipe_from_repo() -> None:
    root = Path(__file__).resolve().parents[2]
    ex = root / "specs/018-hypothesis-research-recipe/examples/extreme-move-eval.yaml"
    if not ex.is_file():
        pytest.skip("example recipe not in tree")
    r = load_recipe_file(ex)
    assert r.version == 1
    assert len(r.steps) == 2
