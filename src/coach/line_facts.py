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
    # Set when the last move captures on a square the other side can take back.
    cut_mid_exchange: Optional[str] = None
    # The cheapest such recapture, and the balance after it.
    recapture_san: Optional[str] = None
    material_after_recapture: int = 0

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

        # The change and the resulting balance are stated separately: "White
        # ends up 3 pawns ahead" was read as the balance when it meant the
        # gain, in lines that started with Black far ahead.
        if self.material_swing == 0:
            parts.append("material is unchanged over the line")
        else:
            side = "White" if self.material_swing > 0 else "Black"
            parts.append(f"{side} gains {_pawns(abs(self.material_swing))} of material")

        if self.cut_mid_exchange:
            parts.append(
                f"the line stops right after a capture on {self.cut_mid_exchange} that can be "
                "taken back, so the material count leaves out the recapture"
            )

        parts.append(f"afterwards {_balance(self.material_after)}")

        # The count at the end of a line cut mid-exchange was repeated as the
        # outcome: "White ends up 2 pawns behind" in a line White was winning.
        if self.recapture_san:
            side = "White" if self.moves[-1].by_white is False else "Black"
            parts.append(
                f"if {side} takes back with {self.recapture_san}, {_balance(self.material_after_recapture)}"
            )

        return "; ".join(parts)


def _owner(move: "MoveFact") -> str:
    """Whose piece a capture took."""
    return "Black" if move.by_white else "White"


def _balance(balance: int) -> str:
    if balance == 0:
        return "material is level"
    return f"{'White' if balance > 0 else 'Black'} is {_pawns(abs(balance))} ahead"


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
    if facts.moves and facts.moves[-1].captured:
        square = replay.peek().to_square
        recaptures = [m for m in replay.legal_moves if m.to_square == square and replay.is_capture(m)]
        if recaptures:
            facts.cut_mid_exchange = chess.square_name(square)
            cheapest = min(recaptures, key=lambda m: _value(replay.piece_type_at(m.from_square)))
            facts.recapture_san = replay.san(cheapest)
            replay.push(cheapest)
            facts.material_after_recapture = material_balance(replay)
    return facts


def _value(piece_type: int) -> int:
    return PIECE_VALUES.get(piece_type, 100)
