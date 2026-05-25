"""Sync user_insights schema with current model

Revision ID: 0004
Revises: 99221b79d5ec
Create Date: 2026-03-21 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0004'
down_revision = '99221b79d5ec'
branch_labels = None
depends_on = None


def upgrade():
    """Sync user_insights table with current model schema."""
    # Check if we need to migrate from old schema to new schema
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('user_insights')]
    
    # If old schema (has insight_type), migrate to new schema
    if 'insight_type' in columns and 'period_start' not in columns:
        # Drop old columns that don't match new schema
        op.drop_column('user_insights', 'insight_type')
        op.drop_column('user_insights', 'insight_data')
        op.drop_column('user_insights', 'priority')
        op.drop_column('user_insights', 'category')
        op.drop_column('user_insights', 'description')
        op.drop_column('user_insights', 'recommendation')
        op.drop_column('user_insights', 'confidence_score')
        op.drop_column('user_insights', 'expires_at')
        
        # Add new schema columns
        op.add_column('user_insights', sa.Column('period_start', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')))
        op.add_column('user_insights', sa.Column('period_end', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')))
        op.add_column('user_insights', sa.Column('analysis_type', sa.String(), nullable=True, server_default='weekly'))
        op.add_column('user_insights', sa.Column('total_games', sa.Integer(), nullable=True, server_default='0'))
        op.add_column('user_insights', sa.Column('games_analyzed', sa.Integer(), nullable=True, server_default='0'))
        op.add_column('user_insights', sa.Column('average_acpl', sa.Float(), nullable=True))
        op.add_column('user_insights', sa.Column('performance_trend', sa.String(), nullable=True))
        op.add_column('user_insights', sa.Column('rating_change', sa.Integer(), nullable=True))
        op.add_column('user_insights', sa.Column('opening_performance', sa.JSON(), nullable=True))
        op.add_column('user_insights', sa.Column('middlegame_performance', sa.JSON(), nullable=True))
        op.add_column('user_insights', sa.Column('endgame_performance', sa.JSON(), nullable=True))
        op.add_column('user_insights', sa.Column('move_quality_stats', sa.JSON(), nullable=True))
        op.add_column('user_insights', sa.Column('frequent_mistakes', sa.JSON(), nullable=True))
        op.add_column('user_insights', sa.Column('opening_repertoire', sa.JSON(), nullable=True))
        op.add_column('user_insights', sa.Column('time_management', sa.JSON(), nullable=True))
        op.add_column('user_insights', sa.Column('recommendations', sa.JSON(), nullable=True))
        op.add_column('user_insights', sa.Column('focus_areas', sa.JSON(), nullable=True))
        op.add_column('user_insights', sa.Column('improvement_metrics', sa.JSON(), nullable=True))
        op.add_column('user_insights', sa.Column('goals_progress', sa.JSON(), nullable=True))
        op.add_column('user_insights', sa.Column('report_generated', sa.Boolean(), nullable=True, server_default='false'))
        op.add_column('user_insights', sa.Column('report_path', sa.String(), nullable=True))
    
    # Add Phase 1 enhanced recommendation columns (works for both old and new schema)
    is_postgresql = bind.dialect.name == 'postgresql'
    
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
        op.add_column('user_insights', 
            sa.Column('recommendation_scores', sa.JSON(), nullable=True)
        )
        op.add_column('user_insights', 
            sa.Column('focus_areas_detailed', sa.JSON(), nullable=True)
        )
        op.add_column('user_insights', 
            sa.Column('pattern_matches', sa.JSON(), nullable=True)
        )
    
    # Add index
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
    """Remove enhanced recommendation fields."""
    op.drop_index('idx_user_insights_user_period', 'user_insights')
    op.drop_column('user_insights', 'pattern_matches')
    op.drop_column('user_insights', 'focus_areas_detailed')
    op.drop_column('user_insights', 'recommendation_scores')
