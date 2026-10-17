"""Material and pawn structure, counted from the board.

After the piece relations went in, most of the remaining false claims about the
current position were counts: "material is level" with Black a bishop up,
"Black has doubled c-pawns" with one c-pawn on the board. A language model
miscounts a listing of thirty pieces; the board does not.
"""

from typing import Dict, List, Set

import chess

from src.coach.line_facts import PIECE_VALUES, material_balance

HEADER = "MATERIAL AND PAWNS (counted from the board - do not count these yourself):"

_ORDER = (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN)


def _side(color: chess.Color) -> str:
    return "White" if color == chess.WHITE else "Black"


def _inventory(board: chess.Board, color: chess.Color) -> str:
    parts = []
    for piece_type in _ORDER:
        count = len(board.pieces(piece_type, color))
        if count:
            name = chess.piece_name(piece_type).capitalize()
            parts.append(name if count == 1 else f"{count} {name}s")
    points = sum(PIECE_VALUES[t] * len(board.pieces(t, color)) for t in _ORDER)
    return f"{_side(color)} has {', '.join(parts) or 'only the King'} ({points} points)"


def _balance(board: chess.Board) -> str:
    balance = material_balance(board)
    if balance == 0:
        return "material is level"
    count = abs(balance)
    return f"{'White' if balance > 0 else 'Black'} is {count} pawn{'s' if count != 1 else ''} ahead"


def _files(board: chess.Board, color: chess.Color) -> Dict[int, List[int]]:
    """Squares of this side's pawns, by file, in board order from the side's own end."""
    by_file: Dict[int, List[int]] = {}
    for square in sorted(board.pieces(chess.PAWN, color), reverse=color == chess.BLACK):
        by_file.setdefault(chess.square_file(square), []).append(square)
    return by_file


def _is_passed(board: chess.Board, square: int, color: chess.Color) -> bool:
    file, rank = chess.square_file(square), chess.square_rank(square)
    for enemy in board.pieces(chess.PAWN, not color):
        ahead = chess.square_rank(enemy) > rank if color == chess.WHITE else chess.square_rank(enemy) < rank
        if ahead and abs(chess.square_file(enemy) - file) <= 1:
            return False
    return True


def _names(squares) -> str:
    return ", ".join(chess.square_name(s) for s in squares) or "none"


def _pawn_lines(board: chess.Board, color: chess.Color) -> List[str]:
    by_file = _files(board, color)
    doubled = [
        f"{chess.FILE_NAMES[f]}-file ({_names(squares)})"
        for f, squares in sorted(by_file.items()) if len(squares) > 1
    ]
    pawns = [s for f in sorted(by_file) for s in by_file[f]]
    isolated = [s for s in pawns if not ({chess.square_file(s) - 1, chess.square_file(s) + 1} & by_file.keys())]
    passed = [s for s in pawns if _is_passed(board, s, color)]
    side = _side(color)
    return [
        f"{side} doubled pawns: {', '.join(doubled) or 'none'}",
        f"{side} isolated pawns: {_names(isolated)}",
        f"{side} passed pawns: {_names(passed)}",
    ]


def entries(board: chess.Board) -> List[str]:
    """The facts as lines, without a header, for a position inside a line."""
    white_files, black_files = _files(board, chess.WHITE), _files(board, chess.BLACK)
    open_files = [chess.FILE_NAMES[f] for f in range(8) if f not in white_files and f not in black_files]
    return [
        f"- Material: {_inventory(board, chess.WHITE)}; {_inventory(board, chess.BLACK)}; {_balance(board)}",
        *(f"- {line}" for color in (chess.WHITE, chess.BLACK) for line in _pawn_lines(board, color)),
        f"- Open files (no pawns): {', '.join(open_files) or 'none'}",
    ]


def describe(board: chess.Board) -> str:
    return "\n".join([HEADER, *entries(board)])


def pawn_kinds(board: chess.Board, square: int) -> Set[str]:
    """Which of doubled, isolated and passed the pawn on `square` is."""
    color = board.piece_at(square).color
    by_file = _files(board, color)
    file = chess.square_file(square)
    kinds = set()
    if len(by_file.get(file, [])) > 1:
        kinds.add("doubled")
    if not ({file - 1, file + 1} & by_file.keys()):
        kinds.add("isolated")
    if _is_passed(board, square, color):
        kinds.add("passed")
    return kinds
