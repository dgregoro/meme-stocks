from __future__ import annotations


class DataAccessError(RuntimeError):
    """Raised when a database operation fails."""


class ExternalAPIError(RuntimeError):
    """Raised when an external API call (Reddit, Yahoo, etc.) fails."""


class IngestionAlreadyRunningError(RuntimeError):
    """Raised when intraday ingestion is triggered but another run holds the global lock."""

    def __init__(self, message: str, owner: str | None = None, expires_at: str | None = None) -> None:
        super().__init__(message)
        self.owner = owner
        self.expires_at = expires_at
