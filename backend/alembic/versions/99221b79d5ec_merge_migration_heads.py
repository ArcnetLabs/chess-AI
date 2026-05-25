"""merge_migration_heads

Revision ID: 99221b79d5ec
Revises: 0003, add_game_filter_indexes
Create Date: 2026-03-21 22:13:55.344994

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '99221b79d5ec'
down_revision = ('0003', 'add_game_filter_indexes')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
