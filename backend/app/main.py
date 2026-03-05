from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .data.database import init_db
from .utils.logging_config import configure_logging

# Import all models so SQLAlchemy knows about them for schema creation
from .models import (  # noqa: F401
    intraday_ingest_run,
    intraday_ingest_state,
    job_execution,
    job_lock,
    job_run_history,
    notification,
    paper_trade,
    price_data,
    price_labels,
    reddit_daily_feature,
    reddit_post,
    reddit_symbol_mention,
    stock,
    symbol_universe,
)
from .api import stocks as stocks_api
from .api import sentiment_price as sentiment_price_api
from .api import analysis as analysis_api
from .api import status as status_api
from .api import notifications as notifications_api
from .api import paper_trading as paper_trading_api
from .api import jobs as jobs_api
from .api import symbol_universe as symbol_universe_api
from .api import intraday as intraday_api
from .api import research as research_api
from .services.scheduler_service import SchedulerService


def _make_lifespan(
    scheduler_for_testing: SchedulerService | None = None,
    omit_scheduler: bool = False,
) -> Any:
    """Build lifespan context manager; accepts optional scheduler for testing."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        # Startup
        configure_logging()  # Redirect yfinance/pandas noise to log file, not terminal
        init_db()
        if omit_scheduler:
            scheduler = None
        elif scheduler_for_testing is not None:
            scheduler = scheduler_for_testing
        else:
            scheduler = SchedulerService()
            scheduler.start()
        if scheduler is not None:
            jobs_api.set_scheduler(scheduler)
            app.state.scheduler = scheduler

        yield

        # Shutdown
        if scheduler is not None and scheduler_for_testing is None:
            scheduler.shutdown()
        jobs_api.set_scheduler(None)

    return lifespan


def create_app(
    scheduler_for_testing: SchedulerService | None = None,
    omit_scheduler: bool = False,
) -> FastAPI:
    """Application factory for the FastAPI app.

    Using a factory makes testing and future configuration easier.
    """

    settings = get_settings()
    app = FastAPI(
        title="Meme Stocks Trading App",
        debug=False,
        lifespan=_make_lifespan(scheduler_for_testing, omit_scheduler),
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        """Simple health check endpoint.

        Returns basic status information. This endpoint should not hide
        configuration or startup issues; if the app fails to start due to
        invalid configuration, the whole application will fail fast.
        """

        return {
            "status": "ok",
            "version": settings.app_version,
            "env": "local",
            "log_level": settings.log_level,
        }

    # CORS
    origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routers
    app.include_router(stocks_api.router)
    app.include_router(sentiment_price_api.router)
    app.include_router(analysis_api.router)
    app.include_router(status_api.router)
    app.include_router(notifications_api.router)
    app.include_router(paper_trading_api.router)
    app.include_router(jobs_api.router)
    app.include_router(symbol_universe_api.router)
    app.include_router(intraday_api.router)
    app.include_router(research_api.router)

    # Serve frontend static files when running in container (SERVING_FRONTEND=true)
    if os.getenv("SERVING_FRONTEND", "").lower() in ("true", "1", "yes"):
        frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend_dist"
        if frontend_dist.exists():
            app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

            from fastapi.responses import FileResponse

            @app.get("/{full_path:path}")
            async def serve_spa(full_path: str) -> Any:
                """Serve SPA: static files or index.html for client-side routes."""
                if full_path.startswith("api/") or full_path in ("health", "docs", "redoc", "openapi.json"):
                    from fastapi import HTTPException, status

                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
                file_path = frontend_dist / full_path
                if file_path.is_file():
                    return FileResponse(file_path)
                return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()
