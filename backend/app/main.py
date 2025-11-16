from __future__ import annotations

from fastapi import FastAPI

from .config import get_settings


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

    return app


app = create_app()
