"""Mechanical facts about an engine line.

The verifier guarantees that a quoted line was really searched. It says nothing
about the prose wrapped around it, and that prose was wrong in ways the board
settles outright: a check described as "attacking the Black Bishop", a line
said to lead to "exchanges of Queens" in which no queen is ever captured.

Both are decidable by replaying the moves. Deriving them here serves two
purposes - the facts go into the prompt so the model has no need to guess, and
into the verifier so a wrong guess does not reach the player.
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
    # Enemy piece types the moved piece bears on from its destination square.
    # A checking move attacks the king, which is what makes "Bb5+, attacking
    # the Black Bishop" a decidable falsehood rather than loose phrasing.
    attacks: Set[str] = field(default_factory=set)


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
                + ", ".join(f"{m.san} takes a {m.captured}" for m in captures)
            )
        else:
            parts.append("no captures")

        if "queen" not in self.captured_types:
            parts.append("no queens are exchanged")

        # The change and the resulting balance are stated separately: "White
        # ends up 3 pawns ahead" was read as the balance when it meant the
        # gain, in lines that started with Black far ahead.
        if self.material_swing == 0:
            parts.append("material is unchanged over the line")
        else:
            side = "White" if self.material_swing > 0 else "Black"
            parts.append(f"{side} gains {_pawns(abs(self.material_swing))} of material")

        if self.material_after == 0:
            parts.append("afterwards material is level")
        else:
            side = "White" if self.material_after > 0 else "Black"
            parts.append(f"afterwards {side} is {_pawns(abs(self.material_after))} ahead")

        return "; ".join(parts)


def _pawns(count: int) -> str:
    return f"{count} pawn" if count == 1 else f"{count} pawns"


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

        attacked = set()
        for square in replay.attacks(move.to_square):
            piece = replay.piece_at(square)
            if piece is not None and piece.color != mover_is_white:
                attacked.add(chess.piece_name(piece.piece_type))

        facts.moves.append(
            MoveFact(
                san=san,
                is_check=replay.is_check(),
                is_mate=replay.is_checkmate(),
                captured=chess.piece_name(captured_piece) if captured_piece else None,
                by_white=mover_is_white,
                attacks=attacked,
            )
        )

    facts.material_after = material_balance(replay)
    return facts
