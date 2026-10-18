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
    "says nothing about tactics. A factor can favour a side through the other "
    "side's penalty - a badly placed enemy knight favours you under Knights "
    "even if you have none - so each side's own score is given in brackets):"
)
NOT_SCORED = "not scored (Stockfish 16 leaves it out when one side is far ahead in material, and in some endings)"

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
        lines.append(f"- {short.capitalize()} ({scores}): {_verdict(factors, name)}")
    return "\n".join(lines)


def _verdict(factors: Factors, name: str) -> str:
    if name not in factors:
        return NOT_SCORED
    white, black = factors[name]
    net = white - black
    side = "about even" if abs(net) < SHOWN else f"favours {'White' if net > 0 else 'Black'} by {abs(net):.2f}"
    return f"{side} (White {white:+.2f}, Black {black:+.2f})"


def change(end: chess.Board, before: Optional[Factors], after: Optional[Factors]) -> str:
    """What a line does to each factor, from the position now to `end`."""
    if after is None:
        if end.is_check():
            return f"no comparison: the line ends with {_side(end.turn)} in check"
        return "unavailable (Stockfish 16 is not running)"
    if before is None:
        return "no comparison: the current position has no factor scores"

    compared = [name for name in FACTOR_WORDS if name in before and name in after]
    moves = sorted(
        ((_net(after, name) - _net(before, name), FACTOR_WORDS[name][0]) for name in compared),
        key=lambda item: -abs(item[0]),
    )
    shown = [
        f"{short} moves {abs(delta):.2f} towards {'White' if delta > 0 else 'Black'}"
        for delta, short in moves if abs(delta) >= SHOWN
    ]
    text = "; ".join(shown) if shown else f"no factor moves by {SHOWN} or more"
    left_out = [FACTOR_WORDS[name][0] for name in FACTOR_WORDS if name not in compared]
    if left_out:
        text += f"; not compared, as Stockfish 16 did not score them at both ends: {', '.join(left_out)}"
    return text
