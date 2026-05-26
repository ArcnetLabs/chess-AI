"""add player_profiles table

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-26 20:30:00.000000

P1-DB-02 — Player profile schema migration.

Creates versioned longitudinal profile snapshots per user. Each row is an
immutable point-in-time aggregate for coaching memory (LTM tier).

Downgrade note: drops all profile snapshot data. Re-run profile builder
(P1-PP-01) after downgrade→upgrade to repopulate.

No pgvector / embedding columns — Phase 3 semantic_memory handles vectors.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0007"
down_revision = "0006"
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
        "player_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archetype", sa.Text(), nullable=True),
        sa.Column("primary_strengths", json_type, nullable=True),
        sa.Column("primary_weaknesses", json_type, nullable=True),
        sa.Column("style_indicators", json_type, nullable=True),
        sa.Column("time_management_profile", json_type, nullable=True),
        sa.Column("phase_performance", json_type, nullable=True),
        sa.Column("opening_repertoire", json_type, nullable=True),
        sa.Column("tactical_themes", json_type, nullable=True),
        sa.Column("pattern_summary_refs", json_type, nullable=True),
        sa.Column("rating_trends", json_type, nullable=True),
        sa.Column(
            "games_analyzed_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "patterns_detected_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("first_game_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("profile_summary", sa.Text(), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
            "profile_version",
            name="uq_player_profiles_user_version",
        ),
    )
    op.create_index("ix_player_profiles_id", "player_profiles", ["id"], unique=False)
    op.create_index(
        "ix_player_profiles_user_id", "player_profiles", ["user_id"], unique=False
    )
    op.create_index(
        "idx_profile_user_snapshot",
        "player_profiles",
        ["user_id", "snapshot_at"],
        unique=False,
    )
    op.create_index(
        "idx_profile_user_version",
        "player_profiles",
        ["user_id", "profile_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_profile_user_version", table_name="player_profiles")
    op.drop_index("idx_profile_user_snapshot", table_name="player_profiles")
    op.drop_index("ix_player_profiles_user_id", table_name="player_profiles")
    op.drop_index("ix_player_profiles_id", table_name="player_profiles")
    op.drop_table("player_profiles")
