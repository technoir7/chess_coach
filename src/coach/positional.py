"""Positional factors in words: who is ahead in each, and what a line changes.

The scores come from Stockfish 16's hand-written evaluation (see
src/engine/classical.py). The descriptions say what each of its terms
actually scores, read from its source at sf_16, so that the model explains a
factor by what it measures rather than by what the word suggests.

Kept apart from the tactical facts on purpose: these scores are static and
blind to captures and threats, so they say why a quiet move is good, never
whether a tactic works.
"""

from typing import Optional

import chess

from src.engine.classical import Factors

HEADER = (
    "POSITIONAL FACTORS (Stockfish 16's hand-written evaluation, in pawns. It is "
    "static: it scores the position as it stands and does not look ahead, so it "
    "says nothing about tactics):"
)

# Stockfish's term -> (short name, what it scores).
FACTOR_WORDS = {
    "Pawns": ("pawn structure", "isolated, backward, doubled, connected and blocked pawns"),
    "Knights": ("knights", "outposts, shelter behind a pawn, distance from their own king"),
    "Bishops": ("bishops", "own pawns on the bishop's colour, long diagonals, outposts, distance from their own king"),
    "Rooks": ("rooks", "open, half-open and closed files, a rook shut in by its own king"),
    "Queens": ("queen", "exposure to pins and discovered attacks"),
    "Mobility": ("mobility", "safe squares the pieces can move to"),
    "King safety": ("king safety", "pawn cover, enemy pawns advancing on the king, enemy pieces attacking near it"),
    "Passed": ("passed pawns", "how far they have advanced and how free they are to go on"),
    "Space": ("space", "safe squares behind a side's own pawns on the c- to f-files; middlegame only"),
}

# Below this a difference is within the noise of a static evaluation.
SHOWN = 0.15


def _side(color: chess.Color) -> str:
    return "White" if color == chess.WHITE else "Black"


def _net(factors: Factors, name: str) -> float:
    white, black = factors[name]
    return white - black


def _missing(board: chess.Board) -> str:
    if board.is_check():
        return f"none: {_side(board.turn)} is in check, which this evaluation does not score"
    return "unavailable (Stockfish 16 is not running)"


def describe(board: chess.Board, factors: Optional[Factors]) -> str:
    if factors is None:
        return f"{HEADER}\n{_missing(board)}"
    lines = [HEADER]
    for name, (short, scores) in FACTOR_WORDS.items():
        net = _net(factors, name)
        verdict = "about even" if abs(net) < SHOWN else f"{'White' if net > 0 else 'Black'} better by {abs(net):.2f}"
        lines.append(f"- {short.capitalize()} ({scores}): {verdict}")
    return "\n".join(lines)


def change(end: chess.Board, before: Optional[Factors], after: Optional[Factors]) -> str:
    """What a line does to each factor, from the position now to `end`."""
    if after is None:
        if end.is_check():
            return f"no comparison: the line ends with {_side(end.turn)} in check"
        return "unavailable (Stockfish 16 is not running)"
    if before is None:
        return "no comparison: the current position has no factor scores"

    moves = sorted(
        ((_net(after, name) - _net(before, name), short) for name, (short, _) in FACTOR_WORDS.items()),
        key=lambda item: -abs(item[0]),
    )
    shown = [
        f"{short} moves {abs(delta):.2f} towards {'White' if delta > 0 else 'Black'}"
        for delta, short in moves if abs(delta) >= SHOWN
    ]
    return "; ".join(shown) if shown else f"no factor moves by {SHOWN} or more"
