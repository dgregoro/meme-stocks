"""Research API: build dataset and run causal experiments."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.database import get_session
from backend.app.services.dataset_builder_service import build_training_dataset
from backend.app.services.experiments.directionality import run_directionality, DirectionalityResult
from backend.app.services.experiments.event_study import run_event_study, EventStudyResult
from backend.app.services.experiments.predictiveness import run_predictiveness, PredictivenessResult
from backend.app.services.label_service import compute_and_store_forward_returns
from backend.app.utils.api_errors import error_detail

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["research"])


def _resolve_dataset_dir() -> Path:
    """Return absolute path to research dataset directory."""
    settings = get_settings()
    p = Path(settings.research_dataset_dir)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p.resolve()


def _validate_dataset_path(dataset_path: str) -> Path:
    """Validate dataset_path is under allowed directory and file exists.

    Raises HTTPException if invalid.
    """
    allowed = _resolve_dataset_dir()
    try:
        p = Path(dataset_path).resolve()
    except (ValueError, OSError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("ValidationError", f"Invalid dataset path: {e}"),
        ) from e
    try:
        p.resolve().relative_to(allowed)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail(
                "ValidationError",
                f"Dataset path must be under {allowed}",
                details={"allowed_dir": str(allowed)},
            ),
        )
    if not p.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_detail("NotFoundError", f"Dataset file not found: {dataset_path}"),
        )
    return p


# --- Request/Response models ---


class BuildDatasetRequest(BaseModel):
    """Request to build a training dataset."""

    start_day: str = Field(..., description="Start date YYYY-MM-DD")
    end_day: str = Field(..., description="End date YYYY-MM-DD")
    horizon: int = Field(default=5, ge=1, le=30, description="Forward-return horizon in trading days")
    symbols: list[str] | None = Field(default=None, description="Optional symbol filter")


class BuildDatasetResponse(BaseModel):
    """Response from build-dataset."""

    path: str
    rows_written: int
    labels_rows_upserted: int
    features_rows_upserted: int
    git_sha: str | None
    dataset_version: str


class DirectionalityRequest(BaseModel):
    """Request for directionality experiment."""

    dataset_path: str = Field(..., description="Path to CSV dataset")
    k: int = Field(default=5, ge=1, le=50)
    h: int = Field(default=1, ge=1, le=30)


class DirectionalityResponse(BaseModel):
    """Response from directionality experiment."""

    mentions_lead_returns_corr: float | None
    mentions_lead_returns_n: int
    returns_lead_mentions_corr: float | None
    returns_lead_mentions_n: int


class EventStudyRequest(BaseModel):
    """Request for event-study experiment."""

    dataset_path: str = Field(..., description="Path to CSV dataset")
    window: int = Field(default=20, ge=5, le=100)
    threshold: str = Field(default="p95")
    horizon: int = Field(default=5, ge=1, le=30)


class EventStudyResponse(BaseModel):
    """Response from event-study experiment."""

    spike_mean_fwd_return: float | None
    spike_n: int
    non_spike_mean_fwd_return: float | None
    non_spike_n: int
    spread: float | None


class PredictivenessRequest(BaseModel):
    """Request for predictiveness experiment."""

    dataset_path: str = Field(..., description="Path to CSV dataset")
    horizon: int = Field(default=5, ge=1, le=30)
    split_date: str | None = Field(default=None, description="Train/test split date YYYY-MM-DD")


class PredictivenessResponse(BaseModel):
    """Response from predictiveness experiment."""

    baseline_direction_accuracy: float | None
    augmented_direction_accuracy: float | None
    baseline_ridge_rmse: float | None
    augmented_ridge_rmse: float | None
    n_train: int
    n_test: int


# --- Endpoints ---


@router.post("/build-dataset", response_model=BuildDatasetResponse)
def post_build_dataset(
    request: BuildDatasetRequest,
    db: Session = Depends(get_session),
) -> BuildDatasetResponse:
    """Build training dataset: forward returns + price join; write CSV.

    Legacy Reddit feature columns are zeros in the output. Writes to research_dataset_dir.
    """
    try:
        start_d = date.fromisoformat(request.start_day)
        end_d = date.fromisoformat(request.end_day)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("ValidationError", f"Invalid date format: {e}"),
        ) from e

    if start_d > end_d:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("ValidationError", "start_day must be <= end_day"),
        )

    out_dir = _resolve_dataset_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = str(out_dir / f"meme_stocks_dataset_{ts}.csv")

    try:
        labels_stats = compute_and_store_forward_returns(
            db,
            start_d,
            end_d,
            horizons=[1, 5, 10],
        )
        db.commit()

        ds_stats = build_training_dataset(
            db,
            start_d,
            end_d,
            horizon_days=request.horizon,
            symbols=request.symbols,
            output_path=output_path,
            format="csv",
        )
        db.commit()

        dv = ds_stats.get("dataset_version", "")
        git_sha = (str(dv).split("_")[0] or None) if dv else None
        if git_sha == "nogit":
            git_sha = None

        return BuildDatasetResponse(
            path=output_path,
            rows_written=int(ds_stats["rows_written"]),
            labels_rows_upserted=int(labels_stats["rows_upserted"]),
            features_rows_upserted=0,
            git_sha=git_sha,
            dataset_version=str(ds_stats.get("dataset_version", "")),
        )
    except Exception as exc:
        db.rollback()
        logger.error("Build dataset failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("InternalServerError", f"Build dataset failed: {exc}"),
        ) from exc


@router.post("/experiment/directionality", response_model=DirectionalityResponse)
def post_directionality(request: DirectionalityRequest) -> DirectionalityResponse:
    """Run directionality experiment: mentions lead returns vs returns lead mentions."""
    path = _validate_dataset_path(request.dataset_path)
    try:
        result: DirectionalityResult = run_directionality(
            dataset_path=str(path),
            k=request.k,
            h=request.h,
        )
        return DirectionalityResponse(
            mentions_lead_returns_corr=result.mentions_lead_returns_corr,
            mentions_lead_returns_n=result.mentions_lead_returns_n,
            returns_lead_mentions_corr=result.returns_lead_mentions_corr,
            returns_lead_mentions_n=result.returns_lead_mentions_n,
        )
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("ValidationError", str(e)),
        ) from e


@router.post("/experiment/event-study", response_model=EventStudyResponse)
def post_event_study(request: EventStudyRequest) -> EventStudyResponse:
    """Run event study: average forward returns on mention spike vs non-spike days."""
    path = _validate_dataset_path(request.dataset_path)
    try:
        result: EventStudyResult = run_event_study(
            dataset_path=str(path),
            window=request.window,
            threshold=request.threshold,
            horizon=request.horizon,
        )
        return EventStudyResponse(
            spike_mean_fwd_return=result.spike_mean_fwd_return,
            spike_n=result.spike_n,
            non_spike_mean_fwd_return=result.non_spike_mean_fwd_return,
            non_spike_n=result.non_spike_n,
            spread=result.spread,
        )
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("ValidationError", str(e)),
        ) from e


@router.post("/experiment/predictiveness", response_model=PredictivenessResponse)
def post_predictiveness(request: PredictivenessRequest) -> PredictivenessResponse:
    """Run predictiveness experiment: baseline vs augmented out-of-sample."""
    path = _validate_dataset_path(request.dataset_path)
    try:
        result: PredictivenessResult = run_predictiveness(
            dataset_path=str(path),
            horizon=request.horizon,
            split_date=request.split_date,
        )
        return PredictivenessResponse(
            baseline_direction_accuracy=result.baseline_direction_accuracy,
            augmented_direction_accuracy=result.augmented_direction_accuracy,
            baseline_ridge_rmse=result.baseline_ridge_rmse,
            augmented_ridge_rmse=result.augmented_ridge_rmse,
            n_train=result.n_train,
            n_test=result.n_test,
        )
    except (ValueError, FileNotFoundError, ImportError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("ValidationError", str(e)),
        ) from e
