"""Backend Typer CLI (database-backed operations).

Usage::

    python -m backend.app.cli --help

Command modules live under :mod:`backend.app.cli.commands`; ORM imports for
`init_db()` are side-effect imported from :mod:`backend.app.cli.orm_imports`.
"""

from backend.app.cli.main import app, main

__all__ = ["app", "main"]
