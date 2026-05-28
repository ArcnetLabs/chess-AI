"""add training_plans and drill_attempts tables

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-28 20:00:00.000000

P3-TR-01 — Adaptive training schema migration.

Creates relational store for versioned training plans and drill attempts:
  - training_plans: per-user monotonic plan_version snapshots
  - drill_attempts: individual drill lifecycle (plan-linked or ad-hoc)

Downgrade note: drops both tables and all training data. Re-run plan
generator after downgrade→upgrade to repopulate.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0010"
down_revision = "0009"
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
        "training_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="active",
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("focus_pattern_ids", json_type, nullable=True),
        sa.Column("focus_areas", json_type, nullable=True),
        sa.Column(
            "drill_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "completed_drill_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("plan_metadata", json_type, nullable=True),
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
            "plan_version",
            name="uq_training_plans_user_version",
        ),
    )
    op.create_index("ix_training_plans_id", "training_plans", ["id"], unique=False)
    op.create_index(
        "ix_training_plans_user_id", "training_plans", ["user_id"], unique=False
    )
    op.create_index(
        "idx_training_plan_user_version",
        "training_plans",
        ["user_id", "plan_version"],
        unique=False,
    )

    op.create_table(
        "drill_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("training_plan_id", sa.Integer(), nullable=True),
        sa.Column("pattern_id", sa.Integer(), nullable=True),
        sa.Column("drill_type", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("position_fen", sa.Text(), nullable=True),
        sa.Column("expected_answer", sa.Text(), nullable=True),
        sa.Column("user_answer", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("attempt_metadata", json_type, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["training_plan_id"],
            ["training_plans.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pattern_id"],
            ["player_patterns.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_drill_attempts_id", "drill_attempts", ["id"], unique=False)
    op.create_index(
        "ix_drill_attempts_user_id", "drill_attempts", ["user_id"], unique=False
    )
    op.create_index(
        "idx_drill_attempts_user_plan",
        "drill_attempts",
        ["user_id", "training_plan_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_drill_attempts_user_plan", table_name="drill_attempts")
    op.drop_index("ix_drill_attempts_user_id", table_name="drill_attempts")
    op.drop_index("ix_drill_attempts_id", table_name="drill_attempts")
    op.drop_table("drill_attempts")
    op.drop_index("idx_training_plan_user_version", table_name="training_plans")
    op.drop_index("ix_training_plans_user_id", table_name="training_plans")
    op.drop_index("ix_training_plans_id", table_name="training_plans")
    op.drop_table("training_plans")
