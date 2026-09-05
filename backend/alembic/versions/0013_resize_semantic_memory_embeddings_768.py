"""Resize semantic_memory embeddings to 768 dims (gemini-embedding-001).

Revision ID: 0013
Previous revision: 0012
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_semantic_memory_embedding_hnsw"
INDEX_DDL = (
    "CREATE INDEX idx_semantic_memory_embedding_hnsw "
    "ON semantic_memory USING hnsw (embedding vector_cosine_ops) "
    "WITH (m='16', ef_construction='64')"
)


def upgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
    op.execute("ALTER TABLE semantic_memory ALTER COLUMN embedding TYPE vector(768)")
    op.execute(INDEX_DDL)


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
    op.execute("ALTER TABLE semantic_memory ALTER COLUMN embedding TYPE vector(1536)")
    op.execute(INDEX_DDL)
