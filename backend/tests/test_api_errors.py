"""Tests for structured API error helpers."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.app.utils.api_errors import api_error, error_detail, raise_api_error


@pytest.mark.unit
def test_error_detail_with_details() -> None:
    d = error_detail("NOT_FOUND", "missing", {"id": 1})
    assert d["error"] is True
    assert d["error_type"] == "NOT_FOUND"
    assert d["details"] == {"id": 1}


@pytest.mark.unit
def test_api_error_alias_matches_error_detail() -> None:
    a = api_error("X", "msg", {"k": "v"})
    b = error_detail("X", "msg", {"k": "v"})
    assert a == b


@pytest.mark.unit
def test_raise_api_error_http_exception() -> None:
    with pytest.raises(HTTPException) as excinfo:
        raise_api_error(418, "TEAPOT", "short", {"cup": True})
    assert excinfo.value.status_code == 418
    detail = excinfo.value.detail
    assert isinstance(detail, dict)
    assert detail["error_type"] == "TEAPOT"
    assert detail["details"] == {"cup": True}
