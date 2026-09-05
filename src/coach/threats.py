"""Threat detection against a given side.

Threats are derived from the rules of chess - the attack map of the position -
not from an engine's judgement and not from a language model. That keeps them
falsifiable: every threat here names a square you can check by hand.
"""

from typing import List

import chess

# Only used to compare what an exchange wins or loses. The king is excluded
# because it can never be captured.
PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}


def _describe(piece: chess.Piece, square: int) -> str:
    return f"{chess.piece_name(piece.piece_type).capitalize()} on {chess.square_name(square)}"


def _cheapest_attacker_value(board: chess.Board, attacker_color: chess.Color, square: int) -> int:
    values = [
        PIECE_VALUES[board.piece_at(sq).piece_type]
        for sq in board.attackers(attacker_color, square)
        if board.piece_at(sq).piece_type != chess.KING
    ]
    return min(values) if values else 0


def detect_threats(board: chess.Board, defender_color: chess.Color) -> List[str]:
    """Concrete threats against `defender_color` in this position.

    Reports two things an opponent can act on immediately: a piece that is
    attacked and undefended, and a piece defended but attacked by something
    cheaper (losing the exchange). Deeper tactics are the engine's job.
    """
    threats: List[str] = []
    attacker_color = not defender_color

    if board.is_check() and board.turn == defender_color:
        threats.append("The king is in check.")

    for square, piece in board.piece_map().items():
        if piece.color != defender_color or piece.piece_type == chess.KING:
            continue

        attackers = board.attackers(attacker_color, square)
        if not attackers:
            continue

        defenders = board.attackers(defender_color, square)
        description = _describe(piece, square)

        if not defenders:
            threats.append(f"{description} is attacked and undefended.")
            continue

        cheapest = _cheapest_attacker_value(board, attacker_color, square)
        if cheapest and cheapest < PIECE_VALUES[piece.piece_type]:
            threats.append(
                f"{description} is defended, but attacked by a cheaper piece "
                f"- the exchange loses material."
            )

    return threats
