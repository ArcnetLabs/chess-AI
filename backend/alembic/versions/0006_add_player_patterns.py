"""add player_patterns and pattern_occurrences tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-26 16:00:00.000000

P1-DB-01 — Pattern schema migration.

Creates the canonical relational store for detected chess patterns:
  - player_patterns: per-user aggregated pattern intelligence
  - pattern_occurrences: normalized detection events (game + move)

Downgrade note: drops both tables and all pattern data. Re-run pattern
analysis Celery jobs after downgrade→upgrade to repopulate.

Future vector retrieval (Phase 3) references player_patterns.id via
semantic_memory.source_id — no embedding columns added here.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _json_type(is_postgresql: bool):
    if is_postgresql:
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"
    json_type = _json_type(is_postgresql)

    op.create_table(
        "player_patterns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("pattern_type", sa.String(), nullable=False),
        sa.Column("pattern_subtype", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "affected_games_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "affected_games_ratio",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("pattern_description", sa.Text(), nullable=False),
        sa.Column("example_positions", json_type, nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trend_direction", sa.String(), nullable=True),
        sa.Column("is_strength", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("recommended_drill_type", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "pattern_type",
            "pattern_subtype",
            name="uq_player_patterns_user_type_subtype",
        ),
    )
    op.create_index("ix_player_patterns_id", "player_patterns", ["id"], unique=False)
    op.create_index(
        "ix_player_patterns_user_id", "player_patterns", ["user_id"], unique=False
    )
    op.create_index(
        "idx_patterns_user",
        "player_patterns",
        ["user_id", "severity", "confidence_score"],
        unique=False,
    )
    op.create_index(
        "idx_patterns_type",
        "player_patterns",
        ["pattern_type", "pattern_subtype"],
        unique=False,
    )
    op.create_index(
        "idx_patterns_strength",
        "player_patterns",
        ["user_id", "is_strength", "confidence_score"],
        unique=False,
    )
    op.create_index(
        "idx_patterns_user_last_seen",
        "player_patterns",
        ["user_id", "last_seen_at"],
        unique=False,
    )

    op.create_table(
        "pattern_occurrences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pattern_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("move_number", sa.Integer(), nullable=False),
        sa.Column("game_phase", sa.String(), nullable=True),
        sa.Column("fen_before", sa.Text(), nullable=True),
        sa.Column("fen_after", sa.Text(), nullable=True),
        sa.Column("user_move", sa.String(), nullable=True),
        sa.Column("best_move", sa.String(), nullable=True),
        sa.Column("user_eval", sa.Float(), nullable=True),
        sa.Column("best_eval", sa.Float(), nullable=True),
        sa.Column("eval_delta", sa.Float(), nullable=True),
        sa.Column("context_description", sa.Text(), nullable=True),
        sa.Column("detector_metadata", json_type, nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["pattern_id"], ["player_patterns.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "pattern_id",
            "game_id",
            "move_number",
            name="uq_pattern_occurrences_pattern_game_move",
        ),
    )
    op.create_index(
        "ix_pattern_occurrences_id", "pattern_occurrences", ["id"], unique=False
    )
    op.create_index(
        "idx_pattern_occurrences_pattern",
        "pattern_occurrences",
        ["pattern_id", "detected_at"],
        unique=False,
    )
    op.create_index(
        "idx_pattern_occurrences_user_game",
        "pattern_occurrences",
        ["user_id", "game_id"],
        unique=False,
    )
    op.create_index(
        "idx_pattern_occurrences_game",
        "pattern_occurrences",
        ["game_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_pattern_occurrences_game", table_name="pattern_occurrences")
    op.drop_index(
        "idx_pattern_occurrences_user_game", table_name="pattern_occurrences"
    )
    op.drop_index(
        "idx_pattern_occurrences_pattern", table_name="pattern_occurrences"
    )
    op.drop_index("ix_pattern_occurrences_id", table_name="pattern_occurrences")
    op.drop_table("pattern_occurrences")

    op.drop_index("idx_patterns_user_last_seen", table_name="player_patterns")
    op.drop_index("idx_patterns_strength", table_name="player_patterns")
    op.drop_index("idx_patterns_type", table_name="player_patterns")
    op.drop_index("idx_patterns_user", table_name="player_patterns")
    op.drop_index("ix_player_patterns_user_id", table_name="player_patterns")
    op.drop_index("ix_player_patterns_id", table_name="player_patterns")
    op.drop_table("player_patterns")
