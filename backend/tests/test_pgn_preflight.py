"""Tests for the queue-time PGN preflight (the "49 of 50 games" class).

Chess.com keeps a row for games that never produced a move — aborted
tournament pairings. Their PGN is headers only, so the engine pass had nothing
to analyze and failed deterministically, three times over, which is how a
50-game window reported "49 games analyzed" with nothing on screen to explain
it.
"""
import io

import chess.pgn

from app.services.analysis.pgn_preflight import (
    count_mainline_plies,
    has_analyzable_moves,
    identifies_a_game,
)

# The real shape, taken from production: headers only, and the
# [CurrentPosition] tag shows the *starting* position.
HEADERS_ONLY_PGN = (
    '[Event "Live Chess"]\n'
    '[Site "Chess.com"]\n'
    '[Date "2026.09.20"]\n'
    '[Round "-"]\n'
    '[White "GH_Wilder"]\n'
    '[Black "000ZAKARIA000"]\n'
    '[Result "0-1"]\n'
    '[CurrentPosition "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"]\n'
)

PLAYABLE_PGN = (
    '[Event "Live Chess"]\n'
    '[White "GH_Wilder"]\n'
    '[Black "opponent"]\n'
    '[Result "1-0"]\n'
    "\n"
    "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0\n"
)


def test_headers_only_pgn_has_no_analyzable_moves():
    assert has_analyzable_moves(HEADERS_ONLY_PGN) is False
    assert count_mainline_plies(HEADERS_ONLY_PGN) == 0


def test_playable_pgn_is_analyzable():
    assert has_analyzable_moves(PLAYABLE_PGN) is True
    assert count_mainline_plies(PLAYABLE_PGN) == 6


def test_two_ply_game_still_counts():
    """A one-move game is short, not empty — it must still be analyzed."""
    assert has_analyzable_moves('[Event "Live Chess"]\n\n1. e4 e5 0-1') is True


def test_bare_movetext_pgn_still_counts():
    """No tags, but real moves: still analyzed, and the plies are still real."""
    assert has_analyzable_moves('1. e4 e5 0-1') is True
    assert count_mainline_plies('1. e4 e5 0-1') == 2


def test_missing_pgn_is_not_treated_as_no_moves():
    """Unparseable input means "cannot tell", so the game stays queued.

    Dropping a game we simply failed to parse would hide a real bug behind a
    silently smaller analysis window.
    """
    for value in (None, "", "   "):
        assert count_mainline_plies(value) is None
        assert has_analyzable_moves(value) is True


def test_junk_pgn_is_not_treated_as_no_moves():
    """python-chess is lenient: junk parses into an empty, placeholder-tagged game.

    It must not land in the "no moves" bucket — the game would vanish from the
    analysis window without a trace. Only a record that identifies itself
    counts as a game Chess.com stored without moves.
    """
    junk = "not a pgn at all !!"

    assert count_mainline_plies(junk) == 0  # it parses, there is just no game in it
    assert has_analyzable_moves(junk) is True  # ...so it stays queued


def test_a_real_record_is_recognised_by_its_tags():
    """The production case carries tags; junk carries only parser placeholders."""
    aborted = chess.pgn.read_game(io.StringIO(HEADERS_ONLY_PGN))
    junk = chess.pgn.read_game(io.StringIO("hello world"))

    assert identifies_a_game(aborted) is True
    assert identifies_a_game(junk) is False
    # Both parse to zero moves — which is exactly why the tags decide.
    assert count_mainline_plies(HEADERS_ONLY_PGN) == 0
    assert count_mainline_plies("hello world") == 0
