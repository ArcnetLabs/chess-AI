"""Chess events — decisions that mattered, with their evidence.

An event is the unit coaching operates on. It is always derived from stored
move facts by deterministic code (``services/events/``), never declared by an
LLM, and it carries the numeric inputs behind its classification so any claim
built on it can be re-derived from the database.

Severity, concept and detector version are stored alongside the event so that
changing the taxonomy is visible in the data rather than silently rewriting
history.
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
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class ChessEvent(Base):
    """A significant chess decision extracted from one analysed move."""

    __tablename__ = "chess_events"
    __table_args__ = (
        # Re-running detection over the same game must not duplicate events.
        UniqueConstraint("move_id", "event_type", name="uq_chess_events_move_type"),
        Index("ix_chess_events_user_type_phase", "user_id", "event_type", "phase"),
        Index("ix_chess_events_user_concept", "user_id", "concept"),
        Index("ix_chess_events_user_position_key", "user_id", "position_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    move_id = Column(
        Integer,
        ForeignKey("game_moves.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # What happened
    event_type = Column(String(40), nullable=False, index=True)
    concept = Column(String(40), nullable=False)
    severity = Column(String(12), nullable=False)

    # Where
    phase = Column(String(12), nullable=False)
    move_number = Column(Integer, nullable=False)
    position_key = Column(String(40), index=True)
    fen_before = Column(Text)

    # Engine evidence
    played_move = Column(String(10))
    best_move = Column(String(10))
    eval_before_cp = Column(Float)
    cp_loss = Column(Float)

    # Opponent trigger: set when the opponent's previous move is what exposed
    # the weakness (this is how "you struggle when opponents play ...Nd4"
    # becomes answerable).
    opponent_trigger_ply = Column(Integer)
    opponent_move = Column(String(10))

    # Exact numeric inputs behind the classification, for auditability.
    evidence = Column(JSON)

    detector_id = Column(String(40), nullable=False)
    detector_version = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    move = relationship("GameMove", back_populates="events")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<ChessEvent(game={self.game_id} move={self.move_number} "
            f"{self.event_type} {self.severity})>"
        )
