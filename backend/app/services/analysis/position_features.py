"""Deterministic position features for pattern recognition.

Everything here is computed from a ``chess.Board`` with no model and no engine
call, so it is cheap, reproducible, and safe to use as coaching evidence.

Two keys and a small feature set, chosen because pattern detection needs
"similar circumstances" rather than identical boards (see
``docs/architecture/PLAYER_INTELLIGENCE_ARCHITECTURE.md`` §3–4):

* ``position_key``   — normalised placement + castling + en passant + side to
  move. The halfmove/fullmove clocks are excluded so move-order transpositions
  share a key (the standard "same position" notion).
* ``structure_key``  — pawn skeleton + side to move, i.e. the pawn-structure
  hash idea. Cheap bucket for "this kind of position again".
* features           — material balance, king-safety proxies, mobility, hanging
  pieces and whether the side to move has an unanswered threat.

The feature set is deliberately small: every field must be something a
detector actually consumes, and adding one is a deliberate act because it has
to be backfilled.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import chess

# Material values in centipawns, used for the balance feature and for
# distinguishing "material is level" from "a piece is hanging".
PIECE_VALUES: Dict[int, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Total non-pawn, non-king material below which a position is "simplified".
ENDGAME_MATERIAL_THRESHOLD = 1300


def _placement(board: chess.Board) -> str:
    """Piece placement only (no clocks), lower-case for the colour."""
    parts: List[str] = []
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue
        symbol = piece.symbol()
        parts.append(f"{chess.square_name(square)}{symbol}")
    return "".join(sorted(parts))


def position_key(board: chess.Board) -> str:
    """Normalised position identity: placement + rights + side to move.

    The en-passant square is included only when an en-passant capture is
    actually legal. FEN records the square after every double pawn push even
    when nothing can take, and keeping that would make two genuinely identical
    positions (same pieces, same rights, same side to move) look different
    purely because of a move-order difference.
    """
    ep_square = "-"
    if board.ep_square and board.has_legal_en_passant():
        ep_square = chess.square_name(board.ep_square)
    payload = "|".join(
        [
            _placement(board),
            board.castling_xfen() or "-",
            ep_square,
            "w" if board.turn == chess.WHITE else "b",
        ]
    )
    return _digest(payload)


def structure_key(board: chess.Board) -> str:
    """Pawn skeleton identity plus side to move."""
    parts: List[str] = []
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.piece_type != chess.PAWN:
            continue
        parts.append(f"{chess.square_name(square)}{piece.symbol()}")
    turn = "w" if board.turn == chess.WHITE else "b"
    return _digest("|".join(sorted(parts)) + f"|{turn}")


def _digest(payload: str) -> str:
    import hashlib

    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:32]


def material_balance(board: chess.Board) -> int:
    """White-minus-black material in centipawns (positive favours White)."""
    total = 0
    for piece_type, value in PIECE_VALUES.items():
        total += value * len(board.pieces(piece_type, chess.WHITE))
        total -= value * len(board.pieces(piece_type, chess.BLACK))
    return total


def non_pawn_material(board: chess.Board, color: bool) -> int:
    """Non-pawn, non-king material for one side, in centipawns."""
    total = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        total += PIECE_VALUES[piece_type] * len(board.pieces(piece_type, color))
    return total


def is_simplified(board: chess.Board) -> bool:
    """Both sides have little non-pawn material — an endgame-ish position."""
    return (
        non_pawn_material(board, chess.WHITE) <= ENDGAME_MATERIAL_THRESHOLD
        and non_pawn_material(board, chess.BLACK) <= ENDGAME_MATERIAL_THRESHOLD
    )


def queens_off(board: chess.Board) -> bool:
    return not board.pieces(chess.QUEEN, chess.WHITE) and not board.pieces(
        chess.QUEEN, chess.BLACK
    )


def hanging_pieces(board: chess.Board, color: bool) -> List[str]:
    """Squares of ``color``'s pieces that are attacked and not defended.

    A rough but useful proxy for "there is something to win here": the side to
    move can capture on these squares. It deliberately ignores deeper tactics —
    those need the engine, and the engine's own verdict is recorded separately.
    """
    hanging: List[str] = []
    for square, piece in board.piece_map().items():
        if piece.color != color or piece.piece_type == chess.KING:
            continue
        if board.is_attacked_by(not color, square) and not board.is_attacked_by(
            color, square
        ):
            hanging.append(chess.square_name(square))
    return sorted(hanging)


def mobility(board: chess.Board) -> int:
    """Number of legal moves available to the side to move.

    Approximates piece activity; copied out so the board is left untouched.
    """
    return board.legal_moves.count()


def king_attackers(board: chess.Board, color: bool) -> int:
    """How many enemy pieces attack the squares around ``color``'s king."""
    king_square = board.king(color)
    if king_square is None:
        return 0
    zone = {king_square}
    zone.update(board.attacks(king_square))
    attackers = set()
    for square in zone:
        attackers.update(board.attackers(not color, square))
    return len(attackers)


def pawn_shield(board: chess.Board, color: bool) -> int:
    """Pawns still in front of the king (0-3), a simple safety proxy."""
    king_square = board.king(color)
    if king_square is None:
        return 0
    file_index = chess.square_file(king_square)
    rank_index = chess.square_rank(king_square)
    direction = 1 if color == chess.WHITE else -1
    shield = 0
    for file_offset in (-1, 0, 1):
        target_file = file_index + file_offset
        if not 0 <= target_file <= 7:
            continue
        for step in (1, 2):
            rank = rank_index + direction * step
            if not 0 <= rank <= 7:
                break
            piece = board.piece_at(chess.square(target_file, rank))
            if piece is not None and piece.color == color and piece.piece_type == chess.PAWN:
                shield += 1
                break
    return shield


def extract_features(board: chess.Board, *, mover: Optional[bool] = None) -> Dict:
    """Feature dict for one position.

    ``mover`` is the colour that is about to move, from whose perspective the
    threat/king-safety features are expressed. When omitted the side to move is
    used, which is the usual case at analysis time.
    """
    side = board.turn if mover is None else mover
    opponent = not side
    balance = material_balance(board)
    signed = balance if side == chess.WHITE else -balance

    return {
        # Positive = the mover is ahead.
        "material_balance": signed,
        "material_band": _material_band(signed),
        "simplified": is_simplified(board),
        "queens_off": queens_off(board),
        # Threat picture for the mover.
        "mover_hanging": hanging_pieces(board, side),
        "opponent_hanging": hanging_pieces(board, opponent),
        "mover_king_attackers": king_attackers(board, side),
        "opponent_king_attackers": king_attackers(board, opponent),
        "mover_pawn_shield": pawn_shield(board, side),
        "mobility": mobility(board),
    }


def _material_band(signed_balance: int) -> str:
    """Coarse material band, for "similar circumstances" bucketing."""
    magnitude = abs(signed_balance)
    if magnitude < 100:
        return "level"
    if magnitude < 300:
        return "slight"
    if magnitude < 900:
        return "clear"
    return "decisive"
