"""Shared API error response format for consistent error handling."""

from __future__ import annotations


def error_detail(error_type: str, message: str) -> dict[str, bool | str]:
    """Build a standardized error detail dict for HTTPException.

    All API errors should use this format so the frontend can reliably
    extract user-facing messages via detail.message or detail (string fallback).

    Returns:
        Dict with keys: error, error_type, message
    """
    return {
        "error": True,
        "error_type": error_type,
        "message": message,
    }
