"""per-user chess.com game ids

Revision ID: 0014_per_user_game_ids
Revises: 0013_resize_semantic_memory_embeddings_768
Create Date: 2026-09-22

Uniqueness of ``games.chesscom_game_id`` was global, so a second ChessRun
account linking the same Chess.com username matched the first account's rows:
the importer counted them as "updated", added nothing, and the new account had
one game to analyse. The constraint becomes (user_id, chesscom_game_id).
"""

from alembic import op

revision = "0014_per_user_game_ids"
down_revision = "0013_resize_semantic_memory_embeddings_768"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the global unique index; the column keeps a plain index for lookups.
    op.drop_index("ix_games_chesscom_game_id", table_name="games")
    op.create_index("ix_games_chesscom_game_id", "games", ["chesscom_game_id"], unique=False)
    op.create_index(
        "uq_games_user_chesscom_game_id",
        "games",
        ["user_id", "chesscom_game_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_games_user_chesscom_game_id", table_name="games")
    op.drop_index("ix_games_chesscom_game_id", table_name="games")
    # Restoring global uniqueness can fail on data that legitimately shares ids
    # across users; that is the state this migration exists to allow.
    op.create_index("ix_games_chesscom_game_id", "games", ["chesscom_game_id"], unique=True)
