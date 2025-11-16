from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .api import stocks as stocks_api
from .api import sentiment_price as sentiment_price_api
from .api import analysis as analysis_api
from .api import notifications as notifications_api
from .api import paper_trading as paper_trading_api


def create_app() -> FastAPI:
    """Application factory for the FastAPI app.

    Using a factory makes testing and future configuration easier.
    """

    settings = get_settings()
    app = FastAPI(title="Meme Stocks Trading App", debug=False)

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

    return app


app = create_app()
