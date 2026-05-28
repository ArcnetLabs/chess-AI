"""add user_notifications table

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-28 22:00:00.000000

P3-PC-02 — In-app notification feed schema.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0011"
down_revision = "0010"
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
        "user_notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("notification_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("payload_json", json_type, nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_notifications_id", "user_notifications", ["id"], unique=False
    )
    op.create_index(
        "ix_user_notifications_user_id",
        "user_notifications",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "idx_user_notifications_user_created",
        "user_notifications",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_user_notifications_user_read_at",
        "user_notifications",
        ["user_id", "read_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_user_notifications_user_read_at", table_name="user_notifications"
    )
    op.drop_index(
        "idx_user_notifications_user_created", table_name="user_notifications"
    )
    op.drop_index("ix_user_notifications_user_id", table_name="user_notifications")
    op.drop_index("ix_user_notifications_id", table_name="user_notifications")
    op.drop_table("user_notifications")
