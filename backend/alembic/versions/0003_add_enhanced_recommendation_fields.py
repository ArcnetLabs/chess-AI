"""Add enhanced recommendation fields to user_insights table

Revision ID: 0003
Revises: 0002, add_game_filter_indexes
Create Date: 2026-03-21 18:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    """Add enhanced recommendation fields to user_insights table."""
    # Detect database type
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == 'postgresql'
    
    # Add new columns for enhanced recommendations (nullable for backward compatibility)
    # Use JSONB for PostgreSQL, JSON for SQLite
    if is_postgresql:
        op.add_column('user_insights', 
            sa.Column('recommendation_scores', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
        )
        op.add_column('user_insights', 
            sa.Column('focus_areas_detailed', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
        )
        op.add_column('user_insights', 
            sa.Column('pattern_matches', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
        )
    else:
        # SQLite uses JSON type
        op.add_column('user_insights', 
            sa.Column('recommendation_scores', sa.JSON(), nullable=True)
        )
        op.add_column('user_insights', 
            sa.Column('focus_areas_detailed', sa.JSON(), nullable=True)
        )
        op.add_column('user_insights', 
            sa.Column('pattern_matches', sa.JSON(), nullable=True)
        )
    
    # Add index for performance on user_id and period_end queries
    # Note: SQLite doesn't support DESC in index definition, so we use a simpler version
    if is_postgresql:
        op.create_index(
            'idx_user_insights_user_period',
            'user_insights',
            ['user_id', sa.text('period_end DESC')],
            postgresql_using='btree'
        )
    else:
        op.create_index(
            'idx_user_insights_user_period',
            'user_insights',
            ['user_id', 'period_end']
        )


def downgrade():
    """Remove enhanced recommendation fields from user_insights table."""
    # Drop index
    op.drop_index('idx_user_insights_user_period', 'user_insights')
    
    # Drop columns
    op.drop_column('user_insights', 'pattern_matches')
    op.drop_column('user_insights', 'focus_areas_detailed')
    op.drop_column('user_insights', 'recommendation_scores')
