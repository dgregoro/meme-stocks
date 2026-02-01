"""API endpoints for paper trading: trades and portfolio summary."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.paper_trade_repo import PaperTradeRepository
from backend.app.services.paper_trading_service import (
    PortfolioSummary,
    close_trade,
    compute_portfolio_summary,
    create_trade,
)
from backend.app.utils.api_errors import error_detail
from backend.app.utils.errors import DataAccessError


router = APIRouter(prefix="/api", tags=["paper_trading"])


class CreateTradeRequest(BaseModel):
    stock_symbol: str
    action: str
    quantity: int
    price: float
    notes: str | None = None


class TradeResponse(BaseModel):
    id: int
    stock_symbol: str
    action: str
    quantity: int
    entry_price: float
    exit_price: float | None

    model_config = ConfigDict(from_attributes=True)


class CloseTradeRequest(BaseModel):
    exit_price: float


class PortfolioResponse(BaseModel):
    total_positions: int
    open_positions: int
    closed_positions: int
    realized_pl: float
    unrealized_pl: float
    win_rate: float | None = None
    average_win: float | None = None
    average_loss: float | None = None


@router.post("/trades", response_model=TradeResponse, status_code=201)
def post_trade(req: CreateTradeRequest, db: Session = Depends(get_session)) -> TradeResponse:
    """Create a paper trade (buy or sell). Symbol must exist in stocks."""
    try:
        trade = create_trade(
            db,
            symbol=req.stock_symbol,
            action=req.action,
            quantity=req.quantity,
            price=req.price,
            notes=req.notes,
        )
        db.commit()
    except ValueError as ve:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except DataAccessError as dae:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(dae))
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    return TradeResponse.model_validate(trade)


@router.get("/trades", response_model=List[TradeResponse])
def list_trades(db: Session = Depends(get_session)) -> List[TradeResponse]:
    """List all paper trades, most recent first."""
    trades = PaperTradeRepository(db).list()
    return [TradeResponse.model_validate(t) for t in trades]


@router.post("/trades/{trade_id}/close", response_model=TradeResponse)
def post_close_trade(trade_id: int, req: CloseTradeRequest, db: Session = Depends(get_session)) -> TradeResponse:
    try:
        trade = close_trade(db, trade_id, exit_price=req.exit_price)
        db.commit()
    except ValueError as ve:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("ValidationError", str(ve)),
        )
    except DataAccessError as dae:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_detail("NotFoundError", str(dae)),
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("InternalServerError", str(exc)),
        )
    return TradeResponse.model_validate(trade)


@router.get("/portfolio", response_model=PortfolioResponse)
def get_portfolio(db: Session = Depends(get_session)) -> PortfolioResponse:
    """Get portfolio summary: position counts, realized/unrealized P/L, win rate, avg win/loss."""
    summary: PortfolioSummary = compute_portfolio_summary(db)
    return PortfolioResponse(
        total_positions=summary.total_positions,
        open_positions=summary.open_positions,
        closed_positions=summary.closed_positions,
        realized_pl=summary.realized_pl,
        unrealized_pl=summary.unrealized_pl,
        win_rate=summary.win_rate,
        average_win=summary.average_win,
        average_loss=summary.average_loss,
    )
