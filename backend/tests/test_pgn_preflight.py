"""Tests for the queue-time PGN preflight (the "49 of 50 games" class).

Chess.com keeps a row for games that never produced a move — aborted
tournament pairings. Their PGN is headers only, so the engine pass had nothing
to analyze and failed deterministically, three times over, which is how a
50-game window reported "49 games analyzed" with nothing on screen to explain
it.

A one-ply aborted game is the same problem for one of the two players: the
movetext exists, but none of it is theirs. Game 2750 (``1. d4``, ``Termination
"… won - game abandoned"``) was played by a player who had Black, so they made
no move at all — and it was analysed and stored with ``user_acpl = 0.0`` and
``accuracy_percentage = 99.0``, counting as one of the 50 analysed games.
"""
import io

import chess.pgn
import pytest
from loguru import logger

from app.services.analysis.pgn_preflight import (
    NO_MOVES_ERROR,
    NO_USER_MOVES_ERROR,
    count_mainline_plies,
    has_analyzable_moves,
    identifies_a_game,
    preflight_error,
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

# Game 2750's shape: one ply, the player had Black, so they never moved.
ONE_PLY_ABANDONED_PGN = (
    '[Event "Live Chess"]\n'
    '[Site "Chess.com"]\n'
    '[Date "2026.09.20"]\n'
    '[White "FranckRE"]\n'
    '[Black "GH_Wilder"]\n'
    '[Result "1-0"]\n'
    '[Termination "FranckRE won - game abandoned"]\n'
    '[CurrentPosition "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq d3 0 1"]\n'
    "\n"
    "1. d4 1-0\n"
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


class TestOnePlyGamesDependOnThePlayersColor:
    """A game is only analyzable for the player whose moves are in it."""

    def test_a_one_ply_game_is_empty_for_the_player_who_had_black(self):
        """Game 2750: ``1. d4`` and Black never moved.

        Scoring it stored 0.0 ACPL and 99.0% accuracy for a game the player
        never made a move in, and counted it in "Games analyzed: 50".
        """
        assert count_mainline_plies(ONE_PLY_ABANDONED_PGN) == 1
        assert has_analyzable_moves(ONE_PLY_ABANDONED_PGN, "black") is False
        assert preflight_error(ONE_PLY_ABANDONED_PGN, "black") == NO_USER_MOVES_ERROR

    def test_the_same_one_ply_game_is_still_analyzable_for_white(self):
        """White played that ply, so there is a real move of theirs to score."""
        assert has_analyzable_moves(ONE_PLY_ABANDONED_PGN, "white") is True
        assert preflight_error(ONE_PLY_ABANDONED_PGN, "white") is None

    def test_a_two_ply_game_is_analyzable_for_both_colors(self):
        pgn = '[Event "Live Chess"]\n\n1. e4 e5 0-1'

        assert has_analyzable_moves(pgn, "white") is True
        assert has_analyzable_moves(pgn, "black") is True

    def test_the_color_is_case_insensitive_and_optional(self):
        assert has_analyzable_moves(ONE_PLY_ABANDONED_PGN, "BLACK") is False
        # No colour given: the parser cannot tell, so it does not decide.
        assert has_analyzable_moves(ONE_PLY_ABANDONED_PGN) is True
        assert has_analyzable_moves(ONE_PLY_ABANDONED_PGN, None) is True

    def test_an_unknown_color_does_not_drop_the_game(self):
        """A colour we cannot interpret must not shrink the analysis window."""
        assert has_analyzable_moves(ONE_PLY_ABANDONED_PGN, "green") is True
        assert preflight_error(ONE_PLY_ABANDONED_PGN, "green") is None

    def test_the_no_moves_reason_is_unchanged_for_an_empty_record(self):
        """Colour cannot rescue a record with no movetext at all."""
        assert preflight_error(HEADERS_ONLY_PGN, "black") == NO_MOVES_ERROR
        assert preflight_error(HEADERS_ONLY_PGN, "white") == NO_MOVES_ERROR


@pytest.fixture
def logged():
    """The loguru records emitted by the test body.

    loguru does not feed ``caplog``, and the skip log is the whole point of this
    change, so a sink is attached for the duration of the test. The sink is handed a
    ``Message`` — a ``str`` subclass carrying the record — so the record is what is
    collected.
    """
    records: list = []
    sink_id = logger.add(lambda message: records.append(message.record), level="DEBUG")
    try:
        yield records
    finally:
        logger.remove(sink_id)


def _only(records) -> dict:
    assert len(records) == 1, [record["message"] for record in records]
    return records[0]


class TestASkipLeavesATraceInTheLog:
    """Skipping is correct; it must not look like nothing happened.

    Every one of these games used to be queued and fail with a loud ``ERROR`` per
    retry, so the log showed a failure that explained nothing. The skip replaced
    that, but silently: the queues report only a count
    (``games_skipped_no_moves``), which cannot say which game went or why. One
    ``info`` line per refusal fixes that, and the level matters — a skip is the
    system working, not a failure.
    """

    def test_a_game_with_no_moves_is_logged_with_its_id_and_reason(self, logged):
        assert preflight_error(HEADERS_ONLY_PGN, "white", game_id=4242) == NO_MOVES_ERROR

        record = _only(logged)
        assert record["level"].name == "INFO"
        assert "4242" in record["message"]
        assert NO_MOVES_ERROR in record["message"]

    def test_a_game_the_player_never_moved_in_is_logged_with_its_id_and_reason(self, logged):
        assert has_analyzable_moves(ONE_PLY_ABANDONED_PGN, "black", game_id=2750) is False

        record = _only(logged)
        assert record["level"].name == "INFO"
        assert "2750" in record["message"]
        assert NO_USER_MOVES_ERROR in record["message"]

    def test_the_two_reasons_are_told_apart_in_the_log(self, logged):
        """The reason is the useful half: the two skips are different problems."""
        preflight_error(HEADERS_ONLY_PGN, "white", game_id=1)
        preflight_error(ONE_PLY_ABANDONED_PGN, "black", game_id=2)

        messages = [record["message"] for record in logged]
        assert NO_MOVES_ERROR in messages[0]
        assert NO_USER_MOVES_ERROR in messages[1]

    def test_an_analyzable_game_is_not_logged(self, logged):
        assert has_analyzable_moves(PLAYABLE_PGN, "white", game_id=7) is True
        assert logged == []

    def test_a_pgn_we_cannot_read_is_not_logged_as_a_skip(self, logged):
        """It stays queued, so it must not leave a skip line behind it."""
        assert has_analyzable_moves("not a pgn at all !!", "white", game_id=8) is True
        assert has_analyzable_moves(None, "white", game_id=9) is True
        assert logged == []

    def test_a_caller_without_the_id_still_records_the_reason(self, logged):
        """The log line is worth having even when the call site has no id to give."""
        assert preflight_error(HEADERS_ONLY_PGN) == NO_MOVES_ERROR

        record = _only(logged)
        assert record["level"].name == "INFO"
        assert NO_MOVES_ERROR in record["message"]
