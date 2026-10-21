"""Threat detection against a given side.

Threats are derived from the rules of chess - the attack map of the position -
not from an engine's judgement and not from a language model. That keeps them
falsifiable: every threat here names a square you can check by hand.
"""

from typing import List, Optional, Tuple

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


def _cheapest_attacker(board: chess.Board, attacker_color: chess.Color, square: int) -> Optional[int]:
    """The square of the cheapest piece attacking `square`, the king counting
    last since it can only take an undefended piece."""
    attackers = board.attackers(attacker_color, square)
    if not attackers:
        return None
    return min(attackers, key=lambda sq: PIECE_VALUES.get(board.piece_at(sq).piece_type, 100))


def _threatened(board: chess.Board, defender_color: chess.Color) -> List[Tuple[int, int, bool]]:
    """(square, cheapest attacker's square, undefended) for each piece of
    `defender_color` that is attacked and undefended, or attacked by
    something cheaper (losing the exchange)."""
    found = []
    for square, piece in sorted(board.piece_map().items()):
        if piece.color != defender_color or piece.piece_type == chess.KING:
            continue
        attacker = _cheapest_attacker(board, not defender_color, square)
        if attacker is None:
            continue
        undefended = not board.attackers(defender_color, square)
        attacker_type = board.piece_at(attacker).piece_type
        if undefended or (attacker_type != chess.KING
                          and PIECE_VALUES[attacker_type] < PIECE_VALUES[piece.piece_type]):
            found.append((square, attacker, undefended))
    return found


def detect_threats(board: chess.Board, defender_color: chess.Color) -> List[str]:
    """Concrete threats against `defender_color` in this position.

    Reports two things an opponent can act on immediately: a piece that is
    attacked and undefended, and a piece defended but attacked by something
    cheaper (losing the exchange). Deeper tactics are the engine's job.
    """
    threats: List[str] = []
    if board.is_check() and board.turn == defender_color:
        threats.append("The king is in check.")
    for square, _, undefended in _threatened(board, defender_color):
        description = _describe(board.piece_at(square), square)
        if undefended:
            threats.append(f"{description} is attacked and undefended.")
        else:
            threats.append(
                f"{description} is defended, but attacked by a cheaper piece "
                f"- the exchange loses material."
            )
    return threats


HEADER = (
    "THREATS (worked out from the board: a piece is under threat when an enemy "
    "piece attacks it and it is undefended, or the attacker is worth less. "
    "Deeper tactics are in the engine lines):"
)


def _side(color: chess.Color) -> str:
    return "White" if color == chess.WHITE else "Black"


def _against(board: chess.Board, color: chess.Color) -> str:
    # Round 11 said "no immediate threat to either side" with a pawn attacking
    # a knight: the attack was in PIECE RELATIONS, one line in thirty.
    label = f"- Against {_side(color)}{' (to move)' if board.turn == color else ''}: "
    entries = [
        f"{_describe(board.piece_at(square), square)}, attacked by "
        f"{_describe(board.piece_at(attacker), attacker)}, "
        + ("and undefended" if undefended else "which is worth less")
        for square, attacker, undefended in _threatened(board, color)
    ]
    if board.is_check() and board.turn == color:
        entries.insert(0, f"{_side(color)} is in check")
    return label + ("; ".join(entries) or "none")


def describe(board: chess.Board) -> str:
    return "\n".join([HEADER, _against(board, chess.WHITE), _against(board, chess.BLACK)])
