from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    JSON,
    Text,
    Float,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class PlayerPattern(Base):
    """Aggregated chess pattern detected across a player's games.

    Canonical store for pattern intelligence. Downstream consumers:
    - Pattern engine (P1-PR-*): upserts aggregates after detection runs
    - Profile builder (P1-PP-*): reads severity/confidence for snapshots
    - Recommendation engine (P1-RE-*): links recommendations via pattern id
    - Coaching memory (P3-CM-*): ``semantic_memory.content_id`` references this id
    """

    __tablename__ = "player_patterns"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "pattern_type",
            "pattern_subtype",
            name="uq_player_patterns_user_type_subtype",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    pattern_type = Column(String, nullable=False)
    pattern_subtype = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    confidence_score = Column(Float, nullable=False)
    occurrence_count = Column(Integer, nullable=False, default=0)
    affected_games_count = Column(Integer, nullable=False, default=0)
    affected_games_ratio = Column(Float, nullable=False, default=0.0)
    pattern_description = Column(Text, nullable=False)

    example_positions = Column(JSON, nullable=True)
    first_seen_at = Column(DateTime(timezone=True), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    trend_direction = Column(String, nullable=True)
    is_strength = Column(Boolean, default=False, nullable=False)
    recommended_drill_type = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="patterns")
    occurrences = relationship(
        "PatternOccurrence",
        back_populates="pattern",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<PlayerPattern(id={self.id}, user_id={self.user_id}, "
            f"type='{self.pattern_type}/{self.pattern_subtype}')>"
        )


class PatternOccurrence(Base):
    """Single detection event linking a pattern to a game position.

    Normalized occurrence log for longitudinal profiling and idempotent
    pattern persistence. ``example_positions`` on :class:`PlayerPattern`
    holds a denormalized cache; this table is the source of truth.
    """

    __tablename__ = "pattern_occurrences"
    __table_args__ = (
        UniqueConstraint(
            "pattern_id",
            "game_id",
            "move_number",
            name="uq_pattern_occurrences_pattern_game_move",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    pattern_id = Column(
        Integer,
        ForeignKey("player_patterns.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)

    move_number = Column(Integer, nullable=False)
    game_phase = Column(String, nullable=True)
    fen_before = Column(Text, nullable=True)
    fen_after = Column(Text, nullable=True)
    user_move = Column(String, nullable=True)
    best_move = Column(String, nullable=True)
    user_eval = Column(Float, nullable=True)
    best_eval = Column(Float, nullable=True)
    eval_delta = Column(Float, nullable=True)
    context_description = Column(Text, nullable=True)
    detector_metadata = Column(JSON, nullable=True)

    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    pattern = relationship("PlayerPattern", back_populates="occurrences")
    user = relationship("User", back_populates="pattern_occurrences")
    game = relationship("Game", back_populates="pattern_occurrences")

    def __repr__(self) -> str:
        return (
            f"<PatternOccurrence(id={self.id}, pattern_id={self.pattern_id}, "
            f"game_id={self.game_id}, move={self.move_number})>"
        )
