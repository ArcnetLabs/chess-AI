"""Queue-time PGN preflight: does this game have a single move to analyze?

Chess.com stores a row for games that never produced a move — aborted
tournament pairings and the like. Their PGN carries the headers (and often a
``[CurrentPosition]`` tag for the *starting* position) but no movetext at all.

Those games can never be analyzed, and the failure is deterministic, so:

* queueing them burns one of the slots in the player's analysis window, which
  is how a 50-game window reported "49 games analyzed" with no explanation,
* the per-game task retried them three times with a 60-second delay, paying
  ~2 minutes of worker time to fail the same way each time.

The check lives here, next to the analyzer, so the queue and the engine pass
agree: it counts plies with the same parser
(:mod:`app.services.analysis.unified_analyzer`) uses.
"""
from __future__ import annotations

import io
from typing import Optional

import chess.pgn

#: Error text recorded on a game that was queued despite having no moves.
NO_MOVES_ERROR = "Game has no moves to analyze"


def count_mainline_plies(pgn: Optional[str]) -> Optional[int]:
    """Return the number of plies in ``pgn``'s mainline.

    ``None`` means "could not read it" rather than "no moves", and the two must
    not be conflated: a PGN we cannot read is a bug to investigate, not a game
    to silently drop from the player's analysis window.
    """
    return _count_plies(_read_game(pgn))


def has_analyzable_moves(pgn: Optional[str]) -> bool:
    """False only for a real game record that contains no move at all.

    Note that ``chess.pgn.read_game`` is lenient: it never raises for text that
    is not a game, and it fills in placeholder tags rather than leaving them
    out, so junk comes back as a fully "headered" game with no moves — the same
    shape as a genuine aborted game. Only a record that identifies itself (real
    ``Event``/``Site``/``White``/``Black`` tags) is treated as a game Chess.com
    stored without moves.
    """
    game = _read_game(pgn)
    if game is None:
        return True

    plies = _count_plies(game)
    if plies is None or plies > 0:
        return True

    return not identifies_a_game(game)


def identifies_a_game(game: chess.pgn.Game) -> bool:
    """True when the record carries real tags instead of parser placeholders."""
    headers = game.headers
    return any(
        (headers.get(tag) or "").strip() not in ("", "?")
        for tag in ("Event", "Site", "White", "Black")
    )


def _read_game(pgn: Optional[str]) -> Optional[chess.pgn.Game]:
    if not pgn or not pgn.strip():
        return None
    try:
        return chess.pgn.read_game(io.StringIO(pgn))
    except Exception:  # noqa: BLE001 — malformed input is not "no moves"
        return None


def _count_plies(game: Optional[chess.pgn.Game]) -> Optional[int]:
    if game is None:
        return None
    try:
        return sum(1 for _ in game.mainline_moves())
    except Exception:  # noqa: BLE001
        return None
