"""Engine scores as winning chances.

A 300cp loss decides an equal game and barely matters when a rook up, so
mistakes are measured by how much they cut the chance of winning. The curve
is Lichess's (lichess.org/page/accuracy), fitted to its players' games.
"""

import math
from dataclasses import dataclass, field
from typing import Optional, Tuple

import chess

# Beyond 10 pawns, or a forced mate, a game counts as decided either way.
CAP = 1000


@dataclass(frozen=True)
class Eval:
    """An engine's verdict, from White's side: centipawns or moves to mate
    (positive: White mates), plus its best line in UCI."""
    cp: Optional[int] = None
    mate: Optional[int] = None
    pv: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if (self.cp is None) == (self.mate is None):
            raise ValueError("an Eval has a centipawn score or a mate, not both or neither")

    def white_cp(self) -> int:
        if self.mate is not None:
            return CAP if self.mate > 0 else -CAP
        return max(-CAP, min(CAP, self.cp))


def win_percent(evaluation: Eval, side: chess.Color) -> float:
    cp = evaluation.white_cp() * (1 if side == chess.WHITE else -1)
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)
