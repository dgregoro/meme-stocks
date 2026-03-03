"""Tests for run_causal CLI script."""

from __future__ import annotations

import subprocess
import sys


def test_cli_help_runs() -> None:
    """Module wiring works; CLI is import-safe; no accidental import side effects."""
    result = subprocess.run(
        [sys.executable, "-m", "backend.app.scripts.run_causal", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Run causal analysis" in result.stdout
