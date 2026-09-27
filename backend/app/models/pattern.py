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

    # Context-aware evidence (event-driven detectors). Detectors computed an
    # ``evidence`` dict and threw it away before, so the numbers behind a claim
    # could not be re-read from the database; ``opportunity_count`` is the
    # denominator that turns a count into a rate.
    evidence = Column(JSON, nullable=True)
    context_signature = Column(String(160), nullable=True, index=True)
    opportunity_count = Column(Integer, nullable=True)
    occurrence_rate = Column(Float, nullable=True)
    detector_id = Column(String(40), nullable=True)
    detector_version = Column(Integer, nullable=True)

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

    # Link back to the move and event this occurrence came from, so a coach can
    # walk pattern -> event -> move -> engine evaluation.
    move_id = Column(
        Integer,
        ForeignKey("game_moves.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_id = Column(
        Integer,
        ForeignKey("chess_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

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


class PatternRun(Base):
    """One detection run, so pattern history is auditable over time.

    ``player_patterns`` holds a single upserted row per (user, type, subtype), so
    before this table there was no record of what earlier runs found and no way
    to answer "is this getting better?" from run history. Trend is computed from
    the decision series itself (game recency), and this table records what each
    run saw.
    """

    __tablename__ = "pattern_runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    ran_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    detector_version = Column(String(40), nullable=False)
    games_considered = Column(Integer, nullable=False, default=0)
    decisions_considered = Column(Integer, nullable=False, default=0)
    patterns_detected = Column(Integer, nullable=False, default=0)
    strengths_detected = Column(Integer, nullable=False, default=0)
    summary = Column(JSON, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<PatternRun(id={self.id}, user_id={self.user_id}, "
            f"patterns={self.patterns_detected})>"
        )
