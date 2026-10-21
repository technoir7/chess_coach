"""Material and pawn structure, counted from the board.

After the piece relations went in, most of the remaining false claims about the
current position were counts: "material is level" with Black a bishop up,
"Black has doubled c-pawns" with one c-pawn on the board. A language model
miscounts a listing of thirty pieces; the board does not.
"""

from typing import Dict, List

import chess

from src.coach.line_facts import PIECE_VALUES, material_balance, points

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
    return f"{'White' if balance > 0 else 'Black'} is {points(abs(balance))} ahead"


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


def _ahead(square: int, color: chess.Color, files) -> chess.SquareSet:
    """Squares in front of `square`, from its side's point of view, on the given files."""
    rank = chess.square_rank(square)
    ranks = range(rank + 1, 8) if color == chess.WHITE else range(rank - 1, -1, -1)
    return chess.SquareSet(chess.square(f, r) for f in files if 0 <= f < 8 for r in ranks)


def _is_candidate(board: chess.Board, square: int, color: chess.Color) -> bool:
    """Stockfish 16's own test for a pawn it scores as passed (pawns.cpp and
    Evaluation::passed at sf_16): its only stoppers are pawns it can take now,
    or pawns its neighbours outnumber, or - from the fifth rank on - a single
    blocker that a neighbour can help it past. Its last check reads attacks
    off the board as python-chess sees them, without Stockfish's x-rays, so a
    blocked pawn can very rarely come out differently."""
    us, them = color, not color
    up = 8 if us == chess.WHITE else -8
    file = chess.square_file(square)
    ours, theirs = board.pieces(chess.PAWN, us), board.pieces(chess.PAWN, them)
    if _ahead(square, us, [file]) & ours:
        return False

    stoppers = theirs & _ahead(square, us, [file - 1, file, file + 1])
    lever = theirs & chess.SquareSet(chess.BB_PAWN_ATTACKS[us][square])
    push = square + up
    lever_push = theirs & chess.SquareSet(chess.BB_PAWN_ATTACKS[us][push]) if 0 <= push < 64 else chess.SquareSet()
    neighbours = ours & chess.SquareSet(
        chess.square(f, r) for f in (file - 1, file + 1) if 0 <= f < 8 for r in range(8)
    )
    rank = chess.square_rank(square)
    phalanx = [s for s in neighbours if chess.square_rank(s) == rank]
    blocked = theirs & chess.SquareSet([push]) if 0 <= push < 64 else chess.SquareSet()

    if stoppers == lever or (stoppers == lever_push and len(phalanx) >= len(lever_push)):
        return True
    relative_rank = rank if us == chess.WHITE else 7 - rank
    if not blocked or stoppers != blocked or relative_rank < 4:
        return False
    # A neighbour behind it must be able to step up beside it onto a square
    # the enemy pawns do not both hit, and that square must be safe enough
    # for Stockfish's later check.
    for support in (s for s in neighbours if chess.square_rank(s) == rank - (1 if us == chess.WHITE else -1)):
        step = support + up
        hit_by_two_pawns = len(theirs & board.attackers(them, step)) >= 2
        attackers = len(board.attackers(them, step))
        if step not in theirs and not hit_by_two_pawns and not board.piece_at(step) and (
            attackers < 2 or board.is_attacked_by(us, step)
        ):
            return True
    return False


def _outposts(board: chess.Board, color: chess.Color) -> List[str]:
    """Squares on the side's fourth to sixth ranks that one of its pawns
    defends and that no enemy pawn can ever attack: none stands on a
    neighbouring file still short of the square's rank, from where it could
    advance to hit it. Squares holding a pawn are left out. This is the
    textbook definition; Stockfish 16's is looser (it ignores enemy pawns that
    are blocked or backward), so it can score an outpost this does not list."""
    found = []
    for square in chess.SQUARES:
        relative_rank = chess.square_rank(square) if color == chess.WHITE else 7 - chess.square_rank(square)
        if not 3 <= relative_rank <= 5 or board.piece_type_at(square) == chess.PAWN:
            continue
        if not board.attackers(color, square) & board.pieces(chess.PAWN, color):
            continue
        file = chess.square_file(square)
        if _ahead(square, color, [file - 1, file + 1]) & board.pieces(chess.PAWN, not color):
            continue
        piece = board.piece_at(square)
        found.append(chess.square_name(square) + (
            f" ({chess.piece_name(piece.piece_type).capitalize()} on it)" if piece and piece.color == color else ""))
    return found


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
    candidates = [s for s in pawns if s not in passed and _is_candidate(board, s, color)]
    side = _side(color)
    return [
        f"{side} doubled pawns: {', '.join(doubled) or 'none'}",
        f"{side} isolated pawns: {_names(isolated)}",
        f"{side} passed pawns: {_names(passed)}",
        # Round 11 called e5 an outpost with Black's f7 pawn able to hit it from f6.
        f"{side} outposts (squares a {side} pawn defends that no enemy pawn can ever attack): "
        f"{', '.join(_outposts(board, color)) or 'none'}",
        # Stated because Stockfish 16's passed-pawn score counts these too.
        f"{side} candidate passed pawns (not passed yet, but the pawns in the way can be "
        f"taken or outnumbered; Stockfish 16 scores them as passed pawns): {_names(candidates)}",
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

