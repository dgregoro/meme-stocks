"""Cross-split aggregate ranking row for one candidate configuration."""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.data.database import Base


class LeaderFollowerRobustnessAggregate(Base):
    __tablename__ = "leader_follower_robustness_aggregates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("leader_follower_robustness_runs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    params_json: Mapped[str] = mapped_column(Text, nullable=False)
    aggregate_metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    robustness_score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    run = relationship("LeaderFollowerRobustnessRun", back_populates="aggregates")
