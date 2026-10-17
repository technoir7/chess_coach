"""The positions inside an engine line, worked out move by move.

Half of round 3's false claims were about positions the engine reached rather
than the one on the board: "the check forces the king to f8" with three other
legal replies, "castles and connects the rooks" with a bishop still between
them. The prompt gave each line only its checks, captures and material, so the
model pictured the rest itself. Replaying a line costs microseconds, so the
facts for each position in it are stated instead.
"""

from typing import List, Sequence

import chess

from src.coach import relations, structure

INDENT = "      "


def _label(board: chess.Board, san: str) -> str:
    """The move with its number, read before it is played: "15. Nf5" or "15... Nf5"."""
    dots = "." if board.turn == chess.WHITE else "..."
    return f"{board.fullmove_number}{dots} {san}"


def _replies(board: chess.Board) -> str:
    side = "White" if board.turn == chess.WHITE else "Black"
    count = board.legal_moves.count()
    if count == 0:
        return "checkmate" if board.is_checkmate() else "stalemate"
    if count == 1:
        return f"{side} then has 1 legal move, so its reply is forced"
    return f"{side} then has {count} legal moves, so its reply is not forced"


def _moved_squares(board: chess.Board, move: chess.Move) -> List[int]:
    """Where the moved pieces now stand; castling moves the rook as well."""
    if board.is_castling(move):
        rook_file = 5 if chess.square_file(move.to_square) == 6 else 3
        return [move.to_square, chess.square(rook_file, chess.square_rank(move.to_square))]
    return [move.to_square]


def describe(board: chess.Board, line_san: Sequence[str]) -> str:
    """Move-by-move facts for `line_san` from `board`, then the final position.

    Engine lines are legal by construction; a move that will not parse ends the
    walk rather than raising, as line_facts does for the same reason.
    """
    replay = board.copy()
    rendered = [f"{INDENT[:-2]}MOVE BY MOVE (worked out from the board after each move):"]
    for san in line_san:
        try:
            move = replay.parse_san(san)
        except ValueError:
            break
        label = _label(replay, san)
        squares = _moved_squares(replay, move)
        replay.push(move)
        pieces = "; ".join(relations.piece(replay, square) for square in squares)
        rendered.append(f"{INDENT}{label}: {pieces}. {_replies(replay)}.")

    rendered.append(f"{INDENT[:-2]}POSITION AT THE END OF THIS LINE (worked out from the board):")
    rendered += [INDENT + line for line in relations.entries(replay) + structure.entries(replay)]
    return "\n".join(rendered)
