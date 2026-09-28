"""Retrieval over the player's own history.

Three paths, deliberately separate because they answer different questions:

* ``similar_decisions`` — position/event-keyed: *"what have you done in this kind
  of position before?"* Backed by ``game_moves``/``chess_events``.
* ``similar_games`` — game-level: *"have you played this kind of game before, and
  how did it go?"* Anchored on structure or exact position, because feature
  similarity alone cannot tell one game from another (see its docstring).
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
from .similar_games import (
    SimilarGame,
    find_similar_games,
    format_similar_games_for_context,
    summarise_similar_games,
)

__all__ = [
    "DEFAULT_SEMANTIC_MIN_SIMILARITY",
    "MIN_SIMILARITY",
    "SimilarDecision",
    "SimilarGame",
    "find_similar_decisions",
    "find_similar_games",
    "format_similar_decisions_for_context",
    "format_similar_games_for_context",
    "summarise_similar_games",
]
