"""Retrieval over the player's own history.

Two distinct paths, deliberately kept separate because they answer different
questions:

* ``similar_decisions`` — position/event-keyed: *"what have you done in this kind
  of position before?"* Backed by ``game_moves``/``chess_events``.
* ``coaching.retrieval_service`` — text/embedding-keyed over semantic memory:
  *"what have we discussed?"* Unchanged, except that its relevance floor is now
  actually applied (see ``DEFAULT_SEMANTIC_MIN_SIMILARITY``).
"""

from .similar_decisions import (
    DEFAULT_SEMANTIC_MIN_SIMILARITY,
    MIN_SIMILARITY,
    SimilarDecision,
    find_similar_decisions,
    format_similar_decisions_for_context,
)

__all__ = [
    "DEFAULT_SEMANTIC_MIN_SIMILARITY",
    "MIN_SIMILARITY",
    "SimilarDecision",
    "find_similar_decisions",
    "format_similar_decisions_for_context",
]
