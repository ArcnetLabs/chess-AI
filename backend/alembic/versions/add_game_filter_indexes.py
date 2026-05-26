"""Add indexes for game filtering performance

Revision ID: add_game_filter_indexes
Revises: 
Create Date: 2024-02-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_game_filter_indexes'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add indexes for commonly filtered columns (rated indexes omitted — no rated column on games)
    op.create_index("idx_games_user_id", "games", ["user_id"])
    op.create_index("idx_games_time_class", "games", ["time_class"])
    op.create_index("idx_games_end_time", "games", ["end_time"])
    op.create_index("idx_games_is_analyzed", "games", ["is_analyzed"])

    # Composite indexes for common filter combinations
    op.create_index("idx_games_user_time_class", "games", ["user_id", "time_class"])
    op.create_index("idx_games_user_end_time", "games", ["user_id", "end_time"])


def downgrade():
    op.drop_index("idx_games_user_end_time", "games")
    op.drop_index("idx_games_user_time_class", "games")
    op.drop_index("idx_games_is_analyzed", "games")
    op.drop_index("idx_games_end_time", "games")
    op.drop_index("idx_games_time_class", "games")
    op.drop_index("idx_games_user_id", "games")
