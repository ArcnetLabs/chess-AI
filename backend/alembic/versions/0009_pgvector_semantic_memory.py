"""pgvector extension + semantic_memory table

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-28 18:00:00.000000

P3-CM-01 — Coaching memory vector tier schema.

Creates semantic_memory for embedding-backed retrieval (P3-CM-02/03).
PostgreSQL/Supabase: enables pgvector, VECTOR(1536), HNSW cosine index.
SQLite (pytest only): skips extension; embedding stored as TEXT placeholder.

Supabase note: if CREATE EXTENSION fails, enable pgvector in Dashboard →
Database → Extensions before running alembic upgrade head.

Downgrade: drops semantic_memory and indexes; does not drop the vector
extension (shared cluster extension — leave enabled for other apps).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def _json_type(is_postgresql: bool):
    if is_postgresql:
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def _embedding_column(is_postgresql: bool):
    if is_postgresql:
        from pgvector.sqlalchemy import Vector

        return sa.Column("embedding", Vector(1536), nullable=True)
    return sa.Column("embedding", sa.Text(), nullable=True)


def upgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"
    json_type = _json_type(is_postgresql)

    if is_postgresql:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "semantic_memory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("content_id", sa.BigInteger(), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=False),
        _embedding_column(is_postgresql),
        sa.Column("metadata", json_type, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_semantic_memory_id", "semantic_memory", ["id"], unique=False
    )
    op.create_index(
        "ix_semantic_memory_user_id",
        "semantic_memory",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_semantic_memory_content_type",
        "semantic_memory",
        ["content_type"],
        unique=False,
    )
    op.create_index(
        "idx_semantic_memory_user_content_type",
        "semantic_memory",
        ["user_id", "content_type"],
        unique=False,
    )

    if is_postgresql:
        op.execute(
            """
            CREATE INDEX idx_semantic_memory_embedding_hnsw
            ON semantic_memory
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"

    if is_postgresql:
        op.execute(
            "DROP INDEX IF EXISTS idx_semantic_memory_embedding_hnsw"
        )

    op.drop_index(
        "idx_semantic_memory_user_content_type", table_name="semantic_memory"
    )
    op.drop_index(
        "ix_semantic_memory_content_type", table_name="semantic_memory"
    )
    op.drop_index("ix_semantic_memory_user_id", table_name="semantic_memory")
    op.drop_index("ix_semantic_memory_id", table_name="semantic_memory")
    op.drop_table("semantic_memory")
