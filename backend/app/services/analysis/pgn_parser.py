"""PGN parsing utilities for chess game analysis."""

import io
import chess
import chess.pgn
from typing import Optional, List, Tuple
from loguru import logger


class PGNParser:
    """Service for parsing PGN strings and iterating through moves."""
    
    @staticmethod
    def parse_pgn(pgn_text: str) -> Optional[chess.pgn.Game]:
        """
        Parse a PGN string into a chess.pgn.Game object.
        
        Args:
            pgn_text: PGN string
        
        Returns:
            Parsed game object or None if parsing fails
        """
        try:
            game = chess.pgn.read_game(io.StringIO(pgn_text))
            if game is None:
                logger.warning("PGN parsing returned None - empty or invalid PGN")
                return None
            return game
        except Exception as e:
            logger.error(f"Failed to parse PGN: {e}")
            return None
    
    @staticmethod
    def extract_moves(game: chess.pgn.Game) -> List[Tuple[chess.Move, chess.Board, int]]:
        """
        Extract all moves from a game with board states.
        
        Args:
            game: Parsed chess game
        
        Returns:
            List of (move, board_after_move, move_number) tuples
        """
        moves = []
        board = game.board()
        move_number = 1
        
        for move in game.mainline_moves():
            board.push(move)
            moves.append((move, board.copy(), move_number))
            if board.turn == chess.WHITE:
                move_number += 1
        
        return moves
    
    @staticmethod
    def get_fen_before_move(game: chess.pgn.Game, move_index: int) -> Optional[str]:
        """
        Get FEN position before a specific move.
        
        Args:
            game: Parsed chess game
            move_index: Index of the move (0-based)
        
        Returns:
            FEN string or None
        """
        try:
            board = game.board()
            for i, move in enumerate(game.mainline_moves()):
                if i == move_index:
                    return board.fen()
                board.push(move)
            return None
        except Exception as e:
            logger.error(f"Error getting FEN: {e}")
            return None
