"""Per-move facts — the relational substrate for pattern recognition.

Before this table every per-move fact lived in JSON on ``game_analyses``
(``evaluations``, ``blunder_moves``, ``critical_positions``), so cross-game
questions ("when opponents play ...Nd4, what does this player do?") required
re-scanning and flattening the same blobs for every detector, and position
features had nowhere to live.

One row per ply, written during analysis and backfillable from the existing
JSON. See ``services/analysis/move_facts.py`` for the POV conventions, which
matter: ``evaluation_cp`` on the JSON payload is *black-centric*, while the
columns here are always from the moving side's point of view.
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
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class GameMove(Base):
    """One ply of an analysed game, with engine evidence and position features."""

    __tablename__ = "game_moves"
    __table_args__ = (
        # Idempotent re-analysis and backfill both rely on this.
        UniqueConstraint("game_id", "ply", name="uq_game_moves_game_ply"),
        Index("ix_game_moves_user_phase", "user_id", "is_user_move", "phase"),
        Index("ix_game_moves_user_position_key", "user_id", "position_key"),
        Index("ix_game_moves_user_structure_key", "user_id", "structure_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)

    # Identity
    ply = Column(Integer, nullable=False)  # 1-based half-move index
    move_number = Column(Integer, nullable=False)  # full-move number
    color = Column(String(5), nullable=False)  # side that made this move
    is_user_move = Column(Boolean, nullable=False, default=False)

    # Position
    fen_before = Column(Text, nullable=False)
    fen_after = Column(Text, nullable=False)
    # Normalised placement + castling + en-passant + side to move (clocks excluded),
    # so the same position reached by different move orders shares a key.
    position_key = Column(String(40), index=True)
    # Pawn skeleton + side to move — the cheap structural bucket from the
    # chess-programming pawn-hash-table idea.
    structure_key = Column(String(40), index=True)
    # White-minus-black material in centipawns (positive favours White).
    material_balance = Column(Integer)

    # Moves
    move_uci = Column(String(10))
    move_san = Column(String(16))
    best_move_uci = Column(String(10))
    best_pv = Column(JSON)  # first plies of the engine principal variation

    # Engine evidence, always from the moving side's point of view
    eval_before_cp = Column(Float)
    eval_after_cp = Column(Float)
    cp_loss = Column(Float)  # eval_before - eval_after, clamped at zero
    mate_in = Column(Integer)
    is_mate_score = Column(Boolean, nullable=False, default=False)
    engine_depth = Column(Integer)

    # Judgement
    classification = Column(String(16), index=True)
    phase = Column(String(12), index=True)  # canonical move-number phase

    # Derived position features (see services/analysis/position_features.py)
    features = Column(JSON)

    # Opponent context: the ply immediately before this one, when it exists.
    # This is what makes "the opponent played X and you responded Y" queryable.
    prev_ply = Column(Integer)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    game = relationship("Game")
    events = relationship(
        "ChessEvent", back_populates="move", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<GameMove(game={self.game_id} ply={self.ply} {self.move_san} {self.classification})>"
