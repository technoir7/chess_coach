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

Stockfish does not always score every factor, and prints 0.00 for one it
skipped: an ending with a rule of its own (king and queen against king) gets
none, and once one side is far enough ahead it stops after material and
pawns, or before space. Those zeros are not readings, so a skipped factor is
left out rather than passed on as even.
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
# The early exits in Evaluation::value() at sf_16, in its internal units; the
# trace prints values divided by NormalizeToPawnValue.
_LAZY_THRESHOLD_1, _LAZY_THRESHOLD_2 = 3622, 1962
_PAWN_VALUE = 328
_BEFORE_PIECES = ("Material", "Imbalance", "Pawns")
_PIECES_TO_PASSED = ("Knights", "Bishops", "Rooks", "Queens", "Mobility", "King safety", "Passed")

# Material is counted exactly elsewhere, threats are tactics, and Imbalance and
# Winnable have no score per side.
FACTORS = ("Pawns", "Knights", "Bishops", "Rooks", "Queens", "Mobility", "King safety", "Passed", "Space")

_ROW = re.compile(r"^\|\s*([A-Za-z ]+?)\s*\|\s*(\S+)\s+(\S+)\s*\|\s*(\S+)\s+(\S+)\s*\|")

Factors = Dict[str, Tuple[float, float]]


def _non_pawn_material(board: chess.Board) -> int:
    return sum(
        value * len(board.pieces(piece_type, color))
        for piece_type, value in _PIECE_VALUES_MG.items()
        for color in (chess.WHITE, chess.BLACK)
    )


def phase(board: chess.Board) -> int:
    npm = max(_ENDGAME_LIMIT, min(_non_pawn_material(board), _MIDGAME_LIMIT))
    return (npm - _ENDGAME_LIMIT) * PHASE_MIDGAME // (_MIDGAME_LIMIT - _ENDGAME_LIMIT)


def parse_trace(text: str, board: chess.Board) -> Optional[Factors]:
    """Each factor Stockfish scored, as (White, Black) in pawns, or None when
    the side to move is in check, which it declines to evaluate statically."""
    if "none (in check)" in text:
        return None

    rows = {}
    for line in text.splitlines():
        row = _ROW.match(line)
        if row and row.group(1) in FACTORS:
            rows[row.group(1)] = [float(cell) for cell in row.group(2, 3, 4, 5)]
    if not set(FACTORS) <= set(rows):
        raise ValueError(f"unexpected eval output from Stockfish 16: {text[:200]!r}")
    totals = _totals(text)

    if not any(value for row in rows.values() for value in row) and not any(
        any(totals[term]) for term in _BEFORE_PIECES
    ):
        return {}

    p = phase(board)
    margin = _non_pawn_material(board) / 32

    def skipped(threshold: int, terms) -> bool:
        return abs(sum(sum(totals[t]) for t in terms)) * _PAWN_VALUE > threshold + margin

    if skipped(_LAZY_THRESHOLD_1, _BEFORE_PIECES):
        scored = ("Pawns",)
    elif skipped(_LAZY_THRESHOLD_2, _BEFORE_PIECES + _PIECES_TO_PASSED):
        scored = tuple(f for f in FACTORS if f != "Space")
    else:
        scored = FACTORS

    def blend(mg: float, eg: float) -> float:
        return (mg * p + eg * (PHASE_MIDGAME - p)) / PHASE_MIDGAME

    return {name: (blend(*rows[name][:2]), blend(*rows[name][2:])) for name in scored}


_TOTAL = re.compile(r"^\|\s*([A-Za-z ]+?)\s*\|.*\|\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\|\s*$")


def _totals(text: str) -> Dict[str, Tuple[float, float]]:
    """The Total column of each row, (middlegame, endgame)."""
    totals = {}
    for line in text.splitlines():
        row = _TOTAL.match(line)
        if row and row.group(1) in (*_BEFORE_PIECES, *FACTORS):
            totals[row.group(1)] = (float(row.group(2)), float(row.group(3)))
    return totals


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
        return parse_trace(self._read_until("Final evaluation"), board)

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
