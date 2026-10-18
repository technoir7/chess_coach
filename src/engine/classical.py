"""Stockfish 16's hand-written evaluation, read factor by factor.

Stockfish's search is far stronger with its neural network, but the network
gives a number and no reasons. Until version 16 Stockfish also kept its older
evaluation, written by hand and tuned over years of test games, which scores
named positional factors - pawn structure, mobility, king safety, space - for
each side. Its `eval` command prints them, so the coach can say which factor a
move improves instead of guessing why the network likes it. Version 16.1
removed it, so this needs Stockfish 16 exactly, alongside the main engine.

The scores are static: they describe the position as it stands and do not
look ahead, which is why they are used for positional facts only.
"""

import re
import subprocess
from typing import Dict, Optional, Tuple

import chess

# Stockfish's own values, from types.h at sf_16: a position's phase runs from
# 128 (all pieces on) to 0 (no pieces but pawns), and each factor's score is
# its middlegame and endgame values blended by it.
PHASE_MIDGAME = 128
_MIDGAME_LIMIT, _ENDGAME_LIMIT = 15258, 3915
_PIECE_VALUES_MG = {chess.KNIGHT: 781, chess.BISHOP: 825, chess.ROOK: 1276, chess.QUEEN: 2538}

# Material is counted exactly elsewhere, threats are tactics, and Imbalance and
# Winnable have no score per side.
FACTORS = ("Pawns", "Knights", "Bishops", "Rooks", "Queens", "Mobility", "King safety", "Passed", "Space")

_ROW = re.compile(r"^\|\s*([A-Za-z ]+?)\s*\|\s*(\S+)\s+(\S+)\s*\|\s*(\S+)\s+(\S+)\s*\|")

Factors = Dict[str, Tuple[float, float]]


def phase(board: chess.Board) -> int:
    npm = sum(
        value * len(board.pieces(piece_type, color))
        for piece_type, value in _PIECE_VALUES_MG.items()
        for color in (chess.WHITE, chess.BLACK)
    )
    npm = max(_ENDGAME_LIMIT, min(npm, _MIDGAME_LIMIT))
    return (npm - _ENDGAME_LIMIT) * PHASE_MIDGAME // (_MIDGAME_LIMIT - _ENDGAME_LIMIT)


def parse_trace(text: str, phase: int) -> Optional[Factors]:
    """Each factor's (White, Black) score in pawns, or None when the side to
    move is in check, which Stockfish declines to evaluate statically."""
    if "none (in check)" in text:
        return None

    def blend(mg: str, eg: str) -> float:
        return (float(mg) * phase + float(eg) * (PHASE_MIDGAME - phase)) / PHASE_MIDGAME

    factors = {}
    for line in text.splitlines():
        row = _ROW.match(line)
        if row and row.group(1) in FACTORS:
            factors[row.group(1)] = (blend(*row.group(2, 3)), blend(*row.group(4, 5)))
    if set(factors) != set(FACTORS):
        raise ValueError(f"unexpected eval output from Stockfish 16: {text[:200]!r}")
    return factors


class ClassicalEngine:
    """A running Stockfish 16, asked for its factor table. `eval` is not part
    of the UCI protocol, so this talks to the process directly rather than
    through python-chess's engine wrapper."""

    def __init__(self, engine_path: str = "stockfish16"):
        self.engine_path = engine_path
        self._process: Optional[subprocess.Popen] = None

    def start(self) -> None:
        self._process = subprocess.Popen(
            [self.engine_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
        )
        self._send("uci")
        self._read_until("uciok")

    def stop(self) -> None:
        if self._process:
            self._send("quit")
            self._process.wait(timeout=5)
            self._process = None

    def factors(self, board: chess.Board) -> Optional[Factors]:
        if not self._process:
            raise RuntimeError("Stockfish 16 not started")
        self._send(f"position fen {board.fen()}")
        self._send("eval")
        return parse_trace(self._read_until("Final evaluation"), phase(board))

    def _send(self, command: str) -> None:
        self._process.stdin.write(command + "\n")
        self._process.stdin.flush()

    def _read_until(self, marker: str) -> str:
        lines = []
        while True:
            line = self._process.stdout.readline()
            if not line:
                raise RuntimeError(f"Stockfish 16 exited before printing {marker!r}")
            lines.append(line)
            if line.startswith(marker):
                return "".join(lines)
