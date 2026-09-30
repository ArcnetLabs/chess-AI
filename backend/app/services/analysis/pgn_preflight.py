"""Queue-time PGN preflight: does this game have a single move to analyze?

Chess.com stores a row for games that never produced a move — aborted
tournament pairings and the like. Their PGN carries the headers (and often a
``[CurrentPosition]`` tag for the *starting* position) but no movetext at all.

Those games can never be analyzed, and the failure is deterministic, so:

* queueing them burns one of the slots in the player's analysis window, which
  is how a 50-game window reported "49 games analyzed" with no explanation,
* the per-game task retried them three times with a 60-second delay, paying
  ~2 minutes of worker time to fail the same way each time.

A second, quieter shape of the same problem has movetext but none of it the
player's: game 2750 was a one-ply aborted game (``1. d4``, ``Termination "… won
- game abandoned"``) that the player had Black in, so the engine pass had
nothing of theirs to score — and stored it anyway, at ``user_acpl = 0.0`` and
``accuracy_percentage = 99.0``, counting it as an analysed game. Whether a game
is analyzable therefore depends on which colour the player had, which is why the
checks here take an optional ``user_color``.

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

#: Error text recorded on a game whose only moves were the opponent's, so the
#: player never moved in it. Kept distinct from :data:`NO_MOVES_ERROR` because
#: the game record itself is fine — it is the player's side of it that is empty.
NO_USER_MOVES_ERROR = "Game has no moves by the player to analyze"


def count_mainline_plies(pgn: Optional[str]) -> Optional[int]:
    """Return the number of plies in ``pgn``'s mainline.

    ``None`` means "could not read it" rather than "no moves", and the two must
    not be conflated: a PGN we cannot read is a bug to investigate, not a game
    to silently drop from the player's analysis window.
    """
    return _count_plies(_read_game(pgn))


def has_analyzable_moves(
    pgn: Optional[str],
    user_color: Optional[str] = None,
) -> bool:
    """False only for a real game record with no move for the player in it.

    Note that ``chess.pgn.read_game`` is lenient: it never raises for text that
    is not a game, and it fills in placeholder tags rather than leaving them
    out, so junk comes back as a fully "headered" game with no moves — the same
    shape as a genuine aborted game. Only a record that identifies itself (real
    ``Event``/``Site``/``White``/``Black`` tags) is treated as a game Chess.com
    stored without moves.

    ``user_color`` is optional. When it is given, a game the player never moved
    in is not analyzable either — there is no move of theirs to score. Omitting
    it keeps the older, colour-blind answer, which is all the parser can say on
    its own.
    """
    return preflight_error(pgn, user_color) is None


def preflight_error(
    pgn: Optional[str],
    user_color: Optional[str] = None,
) -> Optional[str]:
    """Reason to refuse this game, or ``None`` when it can be analyzed.

    Returns one of :data:`NO_MOVES_ERROR` / :data:`NO_USER_MOVES_ERROR` so every
    caller — the sync queue, the manual queue and the per-game task — records
    the same explanation for the same game. "Cannot tell" is always ``None``:
    an unreadable PGN stays queued rather than disappearing from the window.
    """
    game = _read_game(pgn)
    if game is None:
        return None

    plies = _count_plies(game)
    if plies is None:
        return None

    if plies == 0:
        return NO_MOVES_ERROR if identifies_a_game(game) else None

    return None if _color_moved(plies, user_color) else NO_USER_MOVES_ERROR


def identifies_a_game(game: chess.pgn.Game) -> bool:
    """True when the record carries real tags instead of parser placeholders."""
    headers = game.headers
    return any(
        (headers.get(tag) or "").strip() not in ("", "?")
        for tag in ("Event", "Site", "White", "Black")
    )


def _color_moved(plies: int, user_color: Optional[str]) -> bool:
    """Whether ``user_color`` played at least one of a ``plies``-ply game.

    Ply 1 is always White's, so White needs one ply and Black needs two. An
    unrecognised or missing colour means "cannot tell", and the game stays
    queued — a wrong guess here would drop a real game from the analysis window.
    """
    color = (user_color or "").strip().lower()
    if color == "white":
        return plies >= 1
    if color == "black":
        return plies >= 2
    return True


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
