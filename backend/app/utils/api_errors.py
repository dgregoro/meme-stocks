"""Shared API error response format for consistent error handling (PRD Appendix C)."""

from __future__ import annotations

from typing import Any, NoReturn


def error_detail(
    error_type: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a standardized error detail dict for HTTPException.

    All API errors should use this format so the frontend can reliably
    extract user-facing messages via detail.message or detail (string fallback).

    Returns:
        Dict with keys: error, error_type, message; optional details when provided.
    """
    out: dict[str, Any] = {
        "error": True,
        "error_type": error_type,
        "message": message,
    }
    if details is not None:
        out["details"] = details
    return out


def api_error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Alias for error_detail for consistency with PRD naming (code = error_type)."""
    return error_detail(code, message, details)


def raise_api_error(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> NoReturn:
    """Raise HTTPException with structured envelope. Never returns."""
    from fastapi import HTTPException

    raise HTTPException(status_code=status_code, detail=error_detail(code, message, details))
