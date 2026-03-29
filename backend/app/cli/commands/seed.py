from __future__ import annotations

import typer

from backend.app.data.database import SessionLocal, init_db


def register_seed(app: typer.Typer) -> None:
    seed_app = typer.Typer(help="Bootstrap and seed data.")
    app.add_typer(seed_app, name="seed")

    @seed_app.command("stocks")
    def seed_stocks() -> None:
        """Seed stocks table with symbols from BOOTSTRAP_GROUPS. Idempotent; run before stock-groups."""
        from backend.app.services.stock_seed_service import seed_stocks_for_bootstrap

        init_db()
        db = SessionLocal()
        try:
            result = seed_stocks_for_bootstrap(db)
            db.commit()
            typer.echo(
                f"Stocks seeded: {result['created']} created, " f"{result['total'] - result['created']} already existed"
            )
        finally:
            db.close()

    @seed_app.command("stock-groups")
    def seed_stock_groups() -> None:
        """Seed stock_groups with curated bootstrap data. Idempotent; run 'seed stocks' first."""
        from backend.app.services.stock_group_seed_service import run_bootstrap_seed

        init_db()
        db = SessionLocal()
        try:
            result = run_bootstrap_seed(db)
            db.commit()
            typer.echo(
                f"Stock groups seeded: {result['groups_inserted']} inserted, "
                f"{result['groups_skipped']} skipped (already existed)"
            )
            if result["stocks_created"] > 0:
                typer.echo(f"Created {result['stocks_created']} missing stocks for FK integrity")
            if result["symbols_skipped"]:
                typer.echo("Skipped (with warnings):")
                for s in result["symbols_skipped"]:
                    typer.echo(f"  - {s}")
        finally:
            db.close()
