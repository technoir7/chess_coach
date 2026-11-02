"""A finished game, from one player's side, independent of where it was played."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

import chess


@dataclass(frozen=True)
class Game:
    id: str
    played_at: datetime
    speed: str  # bullet, blitz, rapid, classical, correspondence
    rated: bool
    color: chess.Color  # the player's side
    result: str  # win, loss or draw, for the player
    termination: str  # mate, resign, outoftime, timeout, draw, stalemate, ...
    moves: Tuple[str, ...]  # SAN
    clocks: Optional[Tuple[float, ...]]  # seconds left after each ply
    initial: Optional[int]  # seconds
    increment: Optional[int]
    opening: str
    my_rating: Optional[int]
    opponent_rating: Optional[int]
    url: str

    def boards(self) -> List[chess.Board]:
        """The position before each ply, then the final position: one more
        board than there are moves."""
        board = chess.Board()
        boards = [board.copy()]
        for san in self.moves:
            board.push_san(san)
            boards.append(board.copy())
        return boards

    def my_plies(self) -> range:
        """The plies the player made: even for White, odd for Black."""
        return range(0 if self.color == chess.WHITE else 1, len(self.moves), 2)

    def seconds_left_before(self, ply: int) -> Optional[float]:
        """The mover's clock when ply `ply` began."""
        if self.clocks is None or self.initial is None:
            return None
        return float(self.initial) if ply < 2 else self.clocks[ply - 2]

    def seconds_spent(self, ply: int) -> Optional[float]:
        before = self.seconds_left_before(ply)
        if before is None or ply >= len(self.clocks):
            return None
        return before + (self.increment or 0) - self.clocks[ply]

    def link(self, ply: int) -> str:
        """Lichess counts plies from 1, after the move is made."""
        return f"{self.url}#{ply + 1}"
