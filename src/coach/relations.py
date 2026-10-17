"""What each piece attacks, defends and pins, read off the board.

The eval's commonest remaining mistake was a claim of this kind: a bishop
"protecting" a square of the other colour, a rook "supporting" a pawn through
its own bishop, a "pin" with nothing behind the pinned piece. A language model
reads the position as text and has to trace lines across it; the board settles
each of these outright, so the prompt states them instead.
"""

from typing import List, Optional, Tuple

import chess

from src.coach.line_facts import PIECE_VALUES

HEADER = (
    "PIECE RELATIONS (worked out from the board - use these; do not work out "
    "attacks, defences or pinned pieces yourself):"
)

_DIRECTIONS = {
    chess.BISHOP: [(1, 1), (1, -1), (-1, 1), (-1, -1)],
    chess.ROOK: [(1, 0), (-1, 0), (0, 1), (0, -1)],
}
_DIRECTIONS[chess.QUEEN] = _DIRECTIONS[chess.BISHOP] + _DIRECTIONS[chess.ROOK]


def _name(piece: chess.Piece, square: int) -> str:
    return f"{chess.piece_name(piece.piece_type).capitalize()} on {chess.square_name(square)}"


def _side(color: chess.Color) -> str:
    return "White" if color == chess.WHITE else "Black"


def _value(piece: chess.Piece) -> int:
    return 100 if piece.piece_type == chess.KING else PIECE_VALUES[piece.piece_type]


def piece(board: chess.Board, square: int) -> str:
    """What the piece on `square` attacks and defends, e.g. "White Knight on
    f3 attacks Pawn on e5; defends nothing"."""
    return _piece_line(board, square, board.piece_at(square))[2:].replace(":", "", 1)


def _piece_line(board: chess.Board, square: int, piece: chess.Piece) -> str:
    attacks, defends = [], []
    for target in sorted(board.attacks(square)):
        other = board.piece_at(target)
        if other is None:
            continue
        if other.color != piece.color:
            attacks.append(_name(other, target))
        elif other.piece_type != chess.KING:
            defends.append(_name(other, target))
    return (
        f"- {_side(piece.color)} {_name(piece, square)}: "
        f"attacks {', '.join(attacks) or 'nothing'}; defends {', '.join(defends) or 'nothing'}"
    )


def _walk(board: chess.Board, square: int, step) -> List[int]:
    """Occupied squares along a ray from `square`, nearest first."""
    file, rank = chess.square_file(square), chess.square_rank(square)
    found = []
    while True:
        file, rank = file + step[0], rank + step[1]
        if not (0 <= file < 8 and 0 <= rank < 8):
            return found
        target = chess.square(file, rank)
        if board.piece_at(target) is not None:
            found.append(target)


def _pin(board: chess.Board, square: int, piece: chess.Piece, step) -> Optional[Tuple[int, int]]:
    """A pin along one ray: an enemy piece with a more valuable enemy piece
    straight behind it. Returns the pinned square and the one behind."""
    occupied = _walk(board, square, step)
    if len(occupied) < 2:
        return None
    front, back = (board.piece_at(s) for s in occupied[:2])
    if front.color == piece.color or back.color == piece.color or front.piece_type == chess.KING:
        return None
    if _value(back) <= _value(front):
        return None
    return occupied[0], occupied[1]


def _sorted_pieces(board: chess.Board, color: chess.Color):
    return sorted(
        ((sq, p) for sq, p in board.piece_map().items() if p.color == color),
        key=lambda item: _name(item[1], item[0]),
    )


def pins(board: chess.Board) -> List[Tuple[int, int, int]]:
    """Every pin on the board, as (pinning square, pinned square, square behind)."""
    found = []
    for color in (chess.WHITE, chess.BLACK):
        for square, piece in _sorted_pieces(board, color):
            for step in _DIRECTIONS.get(piece.piece_type, []):
                pin = _pin(board, square, piece, step)
                if pin:
                    found.append((square, *pin))
    return found


def _pin_line(board: chess.Board, pinner: int, pinned: int, behind: int) -> str:
    piece, front, back = (board.piece_at(s) for s in (pinner, pinned, behind))
    text = (
        f"- {_side(piece.color)} {_name(piece, pinner)} pins "
        f"{_side(front.color)} {_name(front, pinned)} to the {_name(back, behind)}"
    )
    if back.piece_type == chess.KING:
        # "Cannot legally move off that line" was read as "cannot move": a pawn
        # pinned along its file was said to be frozen while it could still push.
        text += " (it may only move along that line)"
    return text


def describe(board: chess.Board) -> str:
    return "\n".join([HEADER, *entries(board)])


def entries(board: chess.Board) -> List[str]:
    """The relations as lines, without a header, for a position inside a line."""
    lines = [
        _piece_line(board, square, piece)
        for color in (chess.WHITE, chess.BLACK)
        for square, piece in _sorted_pieces(board, color)
    ]
    pin_lines = [_pin_line(board, *pin) for pin in pins(board)]
    return lines + (pin_lines or ["- Pinned pieces: none."])
