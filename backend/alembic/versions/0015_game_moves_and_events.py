"""game_moves and chess_events

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-24

Introduces the two missing layers of the player-intelligence architecture:

* ``game_moves`` — one row per ply, with engine evidence from the moving side's
  perspective, position identity (``position_key``), structure bucket
  (``structure_key``), material balance and a small set of position features.
  Per-move data previously existed only as JSON on ``game_analyses``.
* ``chess_events`` — deterministic, evidence-carrying "decisions that mattered"
  derived from those moves.

Both tables cascade from ``games`` so a per-user wipe stays complete (the
``game_analyses`` table, by contrast, is reachable only through ``games``).
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_moves",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ply", sa.Integer(), nullable=False),
        sa.Column("move_number", sa.Integer(), nullable=False),
        sa.Column("color", sa.String(length=5), nullable=False),
        sa.Column("is_user_move", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fen_before", sa.Text(), nullable=False),
        sa.Column("fen_after", sa.Text(), nullable=False),
        sa.Column("position_key", sa.String(length=40), nullable=True),
        sa.Column("structure_key", sa.String(length=40), nullable=True),
        sa.Column("material_balance", sa.Integer(), nullable=True),
        sa.Column("move_uci", sa.String(length=10), nullable=True),
        sa.Column("move_san", sa.String(length=16), nullable=True),
        sa.Column("best_move_uci", sa.String(length=10), nullable=True),
        sa.Column("best_pv", sa.JSON(), nullable=True),
        sa.Column("eval_before_cp", sa.Float(), nullable=True),
        sa.Column("eval_after_cp", sa.Float(), nullable=True),
        sa.Column("cp_loss", sa.Float(), nullable=True),
        sa.Column("mate_in", sa.Integer(), nullable=True),
        sa.Column("is_mate_score", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("engine_depth", sa.Integer(), nullable=True),
        sa.Column("classification", sa.String(length=16), nullable=True),
        sa.Column("phase", sa.String(length=12), nullable=True),
        sa.Column("features", sa.JSON(), nullable=True),
        sa.Column("prev_ply", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("game_id", "ply", name="uq_game_moves_game_ply"),
    )
    op.create_index("ix_game_moves_user_phase", "game_moves", ["user_id", "is_user_move", "phase"])
    op.create_index("ix_game_moves_user_position_key", "game_moves", ["user_id", "position_key"])
    op.create_index("ix_game_moves_user_structure_key", "game_moves", ["user_id", "structure_key"])
    op.create_index("ix_game_moves_game_id", "game_moves", ["game_id"])

    op.create_table(
        "chess_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "move_id",
            sa.Integer(),
            sa.ForeignKey("game_moves.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("concept", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=12), nullable=False),
        sa.Column("phase", sa.String(length=12), nullable=False),
        sa.Column("move_number", sa.Integer(), nullable=False),
        sa.Column("position_key", sa.String(length=40), nullable=True),
        sa.Column("fen_before", sa.Text(), nullable=True),
        sa.Column("played_move", sa.String(length=10), nullable=True),
        sa.Column("best_move", sa.String(length=10), nullable=True),
        sa.Column("eval_before_cp", sa.Float(), nullable=True),
        sa.Column("cp_loss", sa.Float(), nullable=True),
        sa.Column("opponent_trigger_ply", sa.Integer(), nullable=True),
        sa.Column("opponent_move", sa.String(length=10), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("detector_id", sa.String(length=40), nullable=False),
        sa.Column("detector_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("move_id", "event_type", name="uq_chess_events_move_type"),
    )
    op.create_index("ix_chess_events_user_type_phase", "chess_events", ["user_id", "event_type", "phase"])
    op.create_index("ix_chess_events_user_concept", "chess_events", ["user_id", "concept"])
    op.create_index("ix_chess_events_user_position_key", "chess_events", ["user_id", "position_key"])
    op.create_index("ix_chess_events_move_id", "chess_events", ["move_id"])


def downgrade() -> None:
    op.drop_table("chess_events")
    op.drop_table("game_moves")
