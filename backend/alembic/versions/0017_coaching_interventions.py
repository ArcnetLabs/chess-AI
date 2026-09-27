"""coaching interventions and profile coaching history

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-27

Adds the coaching-memory layer: what ChessRun offered the player for which
pattern, and the outcome measured from their later games. Also gives profile
snapshots a ``coaching_history`` slice so the coach can see, from the snapshot it
already loads, what has already been tried.
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coaching_interventions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pattern_id",
            sa.Integer(),
            sa.ForeignKey("player_patterns.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("intervention_type", sa.String(length=40), nullable=False),
        sa.Column("concept", sa.String(length=40), nullable=True),
        sa.Column("pattern_subtype", sa.String(length=160), nullable=True),
        sa.Column("context_signature", sa.String(length=160), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="coach"),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column(
            "offered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("outcome", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("outcome_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_evidence", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_coaching_interventions_user_offered",
        "coaching_interventions",
        ["user_id", "offered_at"],
    )
    op.create_index(
        "ix_coaching_interventions_pattern", "coaching_interventions", ["pattern_id"]
    )

    op.add_column("player_profiles", sa.Column("coaching_history", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("player_profiles", "coaching_history")
    op.drop_index("ix_coaching_interventions_pattern", table_name="coaching_interventions")
    op.drop_index(
        "ix_coaching_interventions_user_offered", table_name="coaching_interventions"
    )
    op.drop_table("coaching_interventions")
