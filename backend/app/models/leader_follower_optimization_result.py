"""Single parameter set result within an optimization run."""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.data.database import Base


class LeaderFollowerOptimizationResult(Base):
    """Metrics and robustness score for one grid point."""

    __tablename__ = "leader_follower_optimization_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("leader_follower_optimization_runs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    params_json: Mapped[str] = mapped_column(Text, nullable=False)
    train_metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    validate_metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    test_metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    robustness_score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    run = relationship("LeaderFollowerOptimizationRun", back_populates="results")
