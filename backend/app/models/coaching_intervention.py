"""Coaching interventions and their measured outcomes.

The product question this exists to answer: *"have I taught you this before, and
did it work?"*

Without it, every session starts from scratch and the coach repeats generic
advice. ``chat_sessions`` holds conversations and ``semantic_memory`` holds
compressed exchanges, but neither is a ledger of *what was offered for which
weakness, and what happened next*.

An intervention is recorded when the coach (or a drill plan) offers something for
a pattern. Its outcome is then computed from the player's later games — not
asserted by the model — by comparing the pattern's occurrence rate in the games
after the intervention with the games before it.
"""

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class CoachingIntervention(Base):
    """Something ChessRun offered the player, and how it turned out."""

    __tablename__ = "coaching_interventions"
    __table_args__ = (
        Index("ix_coaching_interventions_user_offered", "user_id", "offered_at"),
        Index("ix_coaching_interventions_pattern", "pattern_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # SET NULL, not CASCADE: if a pattern stops firing and is pruned, the record
    # that the coaching happened must survive — it is history, not derived state.
    pattern_id = Column(
        Integer,
        ForeignKey("player_patterns.id", ondelete="SET NULL"),
        nullable=True,
    )

    # What was offered
    intervention_type = Column(String(40), nullable=False)  # drill | variation_study | concept | position_exercise
    concept = Column(String(40), nullable=True)
    pattern_subtype = Column(String(160), nullable=True)
    context_signature = Column(String(160), nullable=True)
    title = Column(Text, nullable=True)
    payload = Column(JSON, nullable=True)
    source = Column(String(20), nullable=False, default="coach")  # coach | drill | system
    session_id = Column(String(64), nullable=True)

    offered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Outcome, computed from later games
    outcome = Column(String(20), nullable=False, default="unknown")
    outcome_evaluated_at = Column(DateTime(timezone=True), nullable=True)
    outcome_evidence = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    pattern = relationship("PlayerPattern")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<CoachingIntervention(id={self.id}, user_id={self.user_id}, "
            f"{self.intervention_type}, outcome={self.outcome})>"
        )
