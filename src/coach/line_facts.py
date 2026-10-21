"""Mechanical facts about an engine line.

The verifier guarantees that a quoted line was really searched. It says nothing
about the prose wrapped around it, and that prose was wrong in ways the board
settles outright: a check described as "attacking the Black Bishop", a line
said to lead to "exchanges of Queens" in which no queen is ever captured.

Both are decidable by replaying the moves, so the facts go into the prompt and
the model has no need to guess. (The verifier once also read checks and trades
out of the prose against these facts; after round 6 it no longer does.)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Set

import chess

# Only used to describe what an exchange won or lost, never to judge a position.
PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}


@dataclass
class MoveFact:
    san: str
    is_check: bool = False
    is_mate: bool = False
    captured: Optional[str] = None
    by_white: bool = True


@dataclass
class LineFacts:
    moves: List[MoveFact] = field(default_factory=list)
    captured_types: Set[str] = field(default_factory=set)
    # Material balance in pawns, White minus Black, before and after the line.
    material_before: int = 0
    material_after: int = 0

    @property
    def material_swing(self) -> int:
        """Net material change over the line, from White's point of view."""
        return self.material_after - self.material_before

    @property
    def material_won(self) -> int:
        """Material White gains over the line (negative: Black gains). An even
        trade is zero."""
        return self.material_swing

    def checking_moves(self) -> List[str]:
        return [m.san for m in self.moves if m.is_check]

    def capturing_moves(self) -> List[MoveFact]:
        return [m for m in self.moves if m.captured]

    def summary(self) -> str:
        """One line of plain fact, for the prompt.

        States absences as explicitly as presences: the model reached for
        "exchanges of Queens" in a line where nothing was exchanged at all.
        """
        parts = []

        checks = self.checking_moves()
        parts.append(f"checks: {', '.join(checks)}" if checks else "no checks")

        captures = self.capturing_moves()
        if captures:
            parts.append(
                "captures: "
                + ", ".join(f"{m.san} takes a {_owner(m)} {m.captured}" for m in captures)
            )
        else:
            parts.append("no captures")

        # "The queens are traded" was written of a line in which one queen was
        # taken and the other survived, so whose queens go is spelled out.
        queens_lost = {_owner(m) for m in captures if m.captured == "queen"}
        if not queens_lost:
            parts.append("no queens are exchanged")
        elif len(queens_lost) == 1:
            parts.append(f"only {queens_lost.pop()}'s queen is captured, so the queens are not traded")
        else:
            parts.append("both queens are captured, so the queens are traded")

        # The change and the resulting balance are stated separately: "White
        # ends up 3 pawns ahead" was read as the balance when it meant the
        # gain, in lines that started with Black far ahead.
        if self.material_swing == 0:
            parts.append("material is unchanged over the line")
        else:
            side = "White" if self.material_swing > 0 else "Black"
            parts.append(f"{side} gains {points(abs(self.material_swing))} of material")

        parts.append(f"afterwards {_balance(self.material_after)}")

        return "; ".join(parts)


def _owner(move: "MoveFact") -> str:
    """Whose piece a capture took."""
    return "Black" if move.by_white else "White"


def _balance(balance: int) -> str:
    if balance == 0:
        return "material is level"
    return f"{'White' if balance > 0 else 'Black'} is {points(abs(balance))} ahead"


def points(count: int) -> str:
    """Material counted in points (pawn 1, knight and bishop 3, rook 5, queen 9).
    Called "pawns" before, it was repeated as "White is 6 pawns up" for a
    side with a bishop and a knight more."""
    return f"{count} point" if count == 1 else f"{count} points"


def material_balance(board: chess.Board) -> int:
    """White's material minus Black's, in pawns. Promotions count, because the
    board is read rather than captures added up."""
    return sum(
        PIECE_VALUES.get(piece.piece_type, 0) * (1 if piece.color == chess.WHITE else -1)
        for piece in board.piece_map().values()
    )


def describe(board: chess.Board, line_san: Sequence[str]) -> LineFacts:
    """Replay `line_san` from `board` and record what actually happens.

    Stops at the first move that will not play rather than raising: callers
    include the verifier, which is handed text written by a language model.
    """
    replay = board.copy()
    facts = LineFacts(material_before=material_balance(replay))

    for san in line_san:
        try:
            move = replay.parse_san(san)
        except ValueError:
            break

        captured_piece = None
        if replay.is_capture(move):
            if replay.is_en_passant(move):
                captured_piece = chess.PAWN
            else:
                target = replay.piece_at(move.to_square)
                captured_piece = target.piece_type if target else None

        mover_is_white = replay.turn == chess.WHITE
        replay.push(move)

        if captured_piece is not None:
            facts.captured_types.add(chess.piece_name(captured_piece))

        facts.moves.append(
            MoveFact(
                san=san,
                is_check=replay.is_check(),
                is_mate=replay.is_checkmate(),
                captured=chess.piece_name(captured_piece) if captured_piece else None,
                by_white=mover_is_white,
            )
        )

    facts.material_after = material_balance(replay)
    return facts


def end_of(board: chess.Board, line_san: Sequence[str]) -> chess.Board:
    """The position after the line."""
    end = board.copy()
    for san in line_san:
        end.push_san(san)
    return end


def cut(board: chess.Board, pv: Sequence[chess.Move], plies: int, most: int) -> Optional[int]:
    """How many of the engine's moves to show: `plies`, then on while its line
    keeps capturing, giving check or answering one, up to `most`. None when
    the line runs out before then, and the engine must be asked to go on.

    A line cut mid-exchange was once played out here by taking on the last
    square, cheapest piece first. That missed whatever else was loose: round
    8's p095 had White a point up after Nxd5 exd5 Bxd5, where Bxd4 wins the
    knight, and the engine itself plays Nxd5 exd5 Rd1. Where the material
    settles is the engine's call, not a static guess.
    """
    replay = board.copy()
    for shown, move in enumerate(pv):
        if shown == most:
            return most
        if shown >= plies and not _forcing(replay, move):
            return shown
        replay.push(move)
    if replay.is_game_over() or len(pv) >= most:
        return len(pv)
    return None


def _forcing(board: chess.Board, move: chess.Move) -> bool:
    return (
        board.is_capture(move) or board.gives_check(move) or board.is_check()
        or move.promotion is not None
    )
