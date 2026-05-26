"""Tests for chess game analysis (unified analyzer path)."""
import io

import chess.pgn
import pytest


@pytest.mark.analysis
@pytest.mark.unit
def test_parse_pgn(sample_game_pgn):
    """Test PGN parsing without touching the engine layer."""
    game = chess.pgn.read_game(io.StringIO(sample_game_pgn))
    assert game is not None
    assert "e4" in sample_game_pgn
    assert "testuser123" in sample_game_pgn
