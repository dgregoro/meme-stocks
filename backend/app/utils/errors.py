from __future__ import annotations


class DataAccessError(RuntimeError):
    """Raised when a database operation fails."""


class ExternalAPIError(RuntimeError):
    """Raised when an external API call (Reddit, Yahoo, etc.) fails."""
