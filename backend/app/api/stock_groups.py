"""Read-only API for stock groups (leader-follower candidate universe)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.stock_group_repo import StockGroupRepository
from backend.app.utils.api_errors import error_detail

router = APIRouter(prefix="/api/stock-groups", tags=["stock-groups"])


class GroupSummary(BaseModel):
    """Summary of a single group."""

    group_id: str
    symbol_count: int


class GroupListResponse(BaseModel):
    """Response for listing all groups."""

    total_rows: int
    groups: list[GroupSummary]
    is_empty: bool


class GroupDetailResponse(BaseModel):
    """Response for a single group's symbols."""

    group_id: str
    symbols: list[str]
    symbol_count: int


@router.get("", response_model=GroupListResponse)
def list_stock_groups(db: Session = Depends(get_session)) -> GroupListResponse:
    """List all stock groups with symbol counts.

    Use to inspect whether stock_groups is empty (is_empty=true) or populated.
    Empty stock_groups causes leader-follower to emit zero follower candidates.
    """
    try:
        repo = StockGroupRepository(db)
        total = repo.count_total()
        group_ids = repo.list_group_ids()
        groups = [
            GroupSummary(group_id=gid, symbol_count=len(repo.get_symbols_in_group(gid)))
            for gid in group_ids
        ]
        return GroupListResponse(
            total_rows=total,
            groups=groups,
            is_empty=total == 0,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("InternalServerError", f"Failed to list stock groups: {exc}"),
        ) from exc


@router.get("/{group_id}", response_model=GroupDetailResponse)
def get_stock_group(group_id: str, db: Session = Depends(get_session)) -> GroupDetailResponse:
    """Get symbols in a specific group. Returns 404 if group does not exist."""
    try:
        repo = StockGroupRepository(db)
        symbols = repo.get_symbols_in_group(group_id)
        if not symbols:
            # Check if any group exists with this id (e.g. group exists but is empty)
            group_ids = repo.list_group_ids()
            if group_id not in group_ids:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=error_detail("NotFound", f"Stock group '{group_id}' not found"),
                )
        return GroupDetailResponse(
            group_id=group_id,
            symbols=symbols,
            symbol_count=len(symbols),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("InternalServerError", f"Failed to get stock group: {exc}"),
        ) from exc
