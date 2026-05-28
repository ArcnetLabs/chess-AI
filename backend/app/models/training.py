"""Adaptive training plan and drill attempt schema (P3-TR-01).

Downstream consumers (future):
- Drill generator (P3-TR-02): inserts drill_attempts rows
- Training API (P3-TR-03): CRUD on training_plans and attempt lifecycle
"""
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class TrainingPlan(Base):
    """Versioned adaptive training plan for a user.

    ``plan_version`` is monotonic per user; each new plan increments the version.
    ``focus_pattern_ids`` references ``player_patterns.id`` values (JSON array).
    """

    __tablename__ = "training_plans"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "plan_version",
            name="uq_training_plans_user_version",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    plan_version = Column(Integer, nullable=False)
    status = Column(Text, nullable=False, default="active")
    title = Column(Text, nullable=False)
    focus_pattern_ids = Column(JSON, nullable=True)
    focus_areas = Column(JSON, nullable=True)
    drill_count = Column(Integer, nullable=False, default=0)
    completed_drill_count = Column(Integer, nullable=False, default=0)
    source = Column(Text, nullable=False)
    plan_metadata = Column(JSON, nullable=True)

    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="training_plans")
    drill_attempts = relationship(
        "DrillAttempt",
        back_populates="training_plan",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<TrainingPlan(id={self.id}, user_id={self.user_id}, "
            f"version={self.plan_version}, status='{self.status}')>"
        )


class DrillAttempt(Base):
    """Single drill attempt within or outside a training plan.

    ``training_plan_id`` is nullable for ad-hoc drills. ``pattern_id`` links to
    the targeted weakness when applicable (SET NULL if pattern row is removed).
    """

    __tablename__ = "drill_attempts"
    __table_args__ = (
        Index(
            "idx_drill_attempts_user_plan",
            "user_id",
            "training_plan_id",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    training_plan_id = Column(
        Integer,
        ForeignKey("training_plans.id", ondelete="CASCADE"),
        nullable=True,
    )
    pattern_id = Column(
        Integer,
        ForeignKey("player_patterns.id", ondelete="SET NULL"),
        nullable=True,
    )

    drill_type = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="pending")
    prompt_text = Column(Text, nullable=False)
    position_fen = Column(Text, nullable=True)
    expected_answer = Column(Text, nullable=True)
    user_answer = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    score = Column(Float, nullable=True)
    attempt_metadata = Column(JSON, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="drill_attempts")
    training_plan = relationship("TrainingPlan", back_populates="drill_attempts")
    pattern = relationship("PlayerPattern")

    def __repr__(self) -> str:
        return (
            f"<DrillAttempt(id={self.id}, user_id={self.user_id}, "
            f"drill_type='{self.drill_type}', status='{self.status}')>"
        )
