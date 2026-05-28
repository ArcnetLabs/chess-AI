"""add analysis query indexes

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-28 12:00:00.000000

P1-DB-03 — Indexes for hot analysis/pattern query paths.

Targets:
  - pattern_data.load_pattern_aggregation_input (user_id + is_analyzed + end_time)
  - profile_builder._load_move_quality_totals (user_id + is_analyzed join)
  - analysis_tasks GameAnalysis lookup by game_id
  - analysis API list ordered by created_at

Skips indexes that already exist (Supabase manual schema, UNIQUE on game_id).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _index_names(inspector, table_name: str) -> set[str]:
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def _has_game_id_index(inspector, table_name: str = "game_analyses") -> bool:
    """True when game_id is already indexed (explicit index or UNIQUE constraint)."""
    if "idx_game_analyses_game_id" in _index_names(inspector, table_name):
        return True
    for idx in inspector.get_indexes(table_name):
        columns = idx.get("column_names") or []
        if "game_id" in columns and idx.get("unique"):
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"
    inspector = sa_inspect(bind)

    games_indexes = _index_names(inspector, "games")
    if "idx_games_user_analyzed_end_time" not in games_indexes:
        if is_postgresql:
            op.create_index(
                "idx_games_user_analyzed_end_time",
                "games",
                ["user_id", "is_analyzed", sa.text("end_time DESC NULLS LAST")],
                postgresql_using="btree",
            )
        else:
            op.create_index(
                "idx_games_user_analyzed_end_time",
                "games",
                ["user_id", "is_analyzed", "end_time"],
            )

    if "game_analyses" not in inspector.get_table_names():
        return

    analyses_indexes = _index_names(inspector, "game_analyses")

    if not _has_game_id_index(inspector):
        op.create_index(
            "idx_game_analyses_game_id",
            "game_analyses",
            ["game_id"],
            unique=False,
        )

    if "idx_game_analyses_created_at" not in analyses_indexes:
        if is_postgresql:
            op.create_index(
                "idx_game_analyses_created_at",
                "game_analyses",
                [sa.text("created_at DESC")],
                postgresql_using="btree",
            )
        else:
            op.create_index(
                "idx_game_analyses_created_at",
                "game_analyses",
                ["created_at"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)

    if "game_analyses" in inspector.get_table_names():
        analyses_indexes = _index_names(inspector, "game_analyses")
        if "idx_game_analyses_created_at" in analyses_indexes:
            op.drop_index("idx_game_analyses_created_at", table_name="game_analyses")
        if "idx_game_analyses_game_id" in analyses_indexes:
            op.drop_index("idx_game_analyses_game_id", table_name="game_analyses")

    games_indexes = _index_names(inspector, "games")
    if "idx_games_user_analyzed_end_time" in games_indexes:
        op.drop_index("idx_games_user_analyzed_end_time", table_name="games")
