from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .data.database import init_db
# Import all models so SQLAlchemy knows about them for schema creation
from .models import (  # noqa: F401
    job_execution,
    notification,
    paper_trade,
    price_data,
    reddit_post,
    reddit_symbol_mention,
    stock,
    symbol_universe,
)
from .api import stocks as stocks_api
from .api import sentiment_price as sentiment_price_api
from .api import analysis as analysis_api
from .api import notifications as notifications_api
from .api import paper_trading as paper_trading_api
from .api import jobs as jobs_api
from .api import symbol_universe as symbol_universe_api
from .services.scheduler_service import SchedulerService


def _make_lifespan(
    scheduler_for_testing: SchedulerService | None = None,
    omit_scheduler: bool = False,
):
    """Build lifespan context manager; accepts optional scheduler for testing."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
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

        return {"status": "ok", "env": "local", "log_level": settings.log_level}

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
    app.include_router(notifications_api.router)
    app.include_router(paper_trading_api.router)
    app.include_router(jobs_api.router)
    app.include_router(symbol_universe_api.router)

    return app


app = create_app()
