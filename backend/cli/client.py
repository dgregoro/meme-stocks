"""HTTP client for CLI API requests.

Uses base URL from MEME_STOCKS_API_URL or --base-url.
Handles connection errors and API error responses.
"""

from __future__ import annotations

import os
import sys

import httpx

# Exit codes per PRD
EXIT_SUCCESS = 0
EXIT_CLIENT_ERROR = 1
EXIT_SERVER_ERROR = 2
EXIT_CONNECTION_ERROR = 3


def get_base_url() -> str:
    """Base URL for API from env or default."""
    return os.environ.get("MEME_STOCKS_API_URL", "http://127.0.0.1:8000").rstrip("/")


def _extract_message(detail: object) -> str:
    """Extract human-readable message from API error detail."""
    if isinstance(detail, dict):
        return detail.get("message", detail.get("detail", str(detail)))
    return str(detail)


def request(
    method: str,
    path: str,
    *,
    base_url: str | None = None,
    json: object | None = None,
    params: dict[str, str | int] | None = None,
    timeout: float = 30.0,
) -> httpx.Response:
    """Make HTTP request to API. Raises CLIError on failure."""
    url = f"{(base_url or get_base_url())}{path}"
    try:
        resp = httpx.request(
            method=method,
            url=url,
            json=json,
            params=params,
            timeout=timeout,
        )
        return resp
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
        sys.exit(
            f"Backend not reachable at {url}. Is the server running?\n"
            f"Try: uvicorn backend.app.main:app --host 127.0.0.1 --port 8000\n"
            f"Error: {exc}"
        )


def check_response(resp: httpx.Response) -> None:
    """Check response status. Exit with appropriate code on error."""
    if resp.is_success:
        return
    try:
        data = resp.json()
        detail = data.get("detail", data)
        msg = _extract_message(detail) if isinstance(detail, dict) else str(detail)
    except Exception:
        msg = resp.text or f"HTTP {resp.status_code}"
    print(f"Error: {msg}", file=sys.stderr)
    if 400 <= resp.status_code < 500:
        sys.exit(EXIT_CLIENT_ERROR)
    sys.exit(EXIT_SERVER_ERROR)


def get(
    path: str,
    *,
    base_url: str | None = None,
    params: dict[str, str | int] | None = None,
    timeout: float = 30.0,
) -> httpx.Response:
    """GET request. Exits on connection or API error."""
    resp = request("GET", path, base_url=base_url, params=params, timeout=timeout)
    check_response(resp)
    return resp


def post(
    path: str,
    *,
    json: object | None = None,
    base_url: str | None = None,
    timeout: float = 30.0,
) -> httpx.Response:
    """POST request. Exits on connection or API error."""
    resp = request("POST", path, json=json, base_url=base_url, timeout=timeout)
    check_response(resp)
    return resp
