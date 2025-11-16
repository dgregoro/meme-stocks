from __future__ import annotations


class DataAccessError(RuntimeError):
    """Raised when a database operation fails.

    This wraps lower-level SQLAlchemy errors so that callers can handle
    persistence issues explicitly without relying on SQLAlchemy internals.
    """

    pass
