"""Semantic memory rows for pgvector-backed coaching retrieval (P3-CM-01).

Embeddings are populated by P3-CM-02; similarity search by P3-CM-03.
On PostgreSQL uses ``Vector(1536)`` (OpenAI text-embedding-3-small).
Under pytest/SQLite uses ``Text`` so ``Base.metadata.create_all`` works
without the pgvector extension.
"""
import os

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base

_EMBEDDING_DIM = 1536


def _embedding_column():
    db_url = os.getenv("DATABASE_URL", "")
    if db_url.startswith("sqlite") or os.getenv("TESTING") == "1":
        return Column(Text, nullable=True)
    from pgvector.sqlalchemy import Vector

    return Column(Vector(_EMBEDDING_DIM), nullable=True)


class SemanticMemory(Base):
    """Vector-tier semantic memory for coaching context retrieval.

    ``content_type`` values align with MEMORY_RETRIEVAL_CONTEXT_ARCHITECTURE.md
    (e.g. pattern, coaching, behavioral, game_summary). ``content_id`` links
    back to relational source rows (e.g. ``player_patterns.id``).
    """

    __tablename__ = "semantic_memory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_type = Column(Text, nullable=False, index=True)
    content_id = Column(BigInteger, nullable=True)
    content_text = Column(Text, nullable=False)
    embedding = _embedding_column()
    memory_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="semantic_memories")

    def __repr__(self) -> str:
        return (
            f"<SemanticMemory(id={self.id}, user_id={self.user_id}, "
            f"content_type='{self.content_type}')>"
        )
