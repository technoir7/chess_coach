"""Checks coach output against the position it claims to describe.

The prompts ask the model not to invent moves or calculate variations, but a
prompt is a request, not a guarantee - small local models comply most of the
time and not always. This module is the guarantee: anything the model says
about a move is checked against the legal move list before it reaches the user.
"""

import re
from dataclasses import dataclass, field
from typing import List

import chess

# Piece moves, pawn captures and castling are unambiguous claims about a move.
#
# Bare pawn pushes ("e4") are deliberately NOT matched: they are spelled exactly
# like a square reference, and "the pawn on e4" is ordinary description rather
# than a claimed move. Matching them would reject correct prose constantly, so
# this trades a little recall for precision it can rely on.
_MOVE_PATTERN = re.compile(
    r"\b("
    r"O-O-O|O-O|0-0-0|0-0"          # castling
    r"|[KQRBN][a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?"   # piece moves
    r"|[a-h]x[a-h][1-8](?:=[QRBN])?"                  # pawn captures
    r")[+#]?"
)

# A move number followed immediately by a move - "1. Bxb5" - rather than by
# prose, which is how a numbered list of advice legitimately looks.
_VARIATION_PATTERN = re.compile(
    r"\b\d+\s*\.\s*(?:\.\.\.\s*)?"
    r"(?:O-O-O|O-O|[KQRBN][a-h]?[1-8]?x?[a-h][1-8]|[a-h]x?[a-h]?[1-8])[+#]?"
)


@dataclass
class VerificationResult:
    ok: bool
    violations: List[str] = field(default_factory=list)


def _claimable_san(board: chess.Board) -> set:
    """Every move actually available in this position, for either side.

    A coach legitimately says "Black can answer Nc6" while it is White to move.
    That claim is checkable against the position, so it counts as verified; a
    move available to neither side is an invention. Restricting this to the
    side to move would reject correct commentary about the opponent's options.
    """
    san = {board.san(move) for move in board.legal_moves}

    # A null move hands the turn over so the opponent's replies can be named.
    # It is not available out of check, where the side to move must respond.
    if not board.is_check():
        mirror = board.copy()
        mirror.push(chess.Move.null())
        san |= {mirror.san(move) for move in mirror.legal_moves}

    return san


def find_illegal_moves(text: str, board: chess.Board) -> List[str]:
    """Distinct moves named in `text` that are not legal in `board`.

    Deduplicated: a move repeated four times is one invention, not four.
    """
    legal = _claimable_san(board)
    # Compare with check/mate suffixes stripped: the model writing "Qxf7#" for a
    # move python-chess renders "Qxf7" is a notation difference, not a lie.
    legal_bare = {san.rstrip("+#") for san in legal}

    illegal = []
    for match in _MOVE_PATTERN.finditer(text):
        claimed = match.group(0)
        bare = claimed.rstrip("+#").replace("0", "O")
        if bare not in legal_bare and claimed not in legal and claimed not in illegal:
            illegal.append(claimed)
    return illegal


def find_variation_lines(text: str) -> List[str]:
    """Numbered move sequences, which the coach is never allowed to produce."""
    return _VARIATION_PATTERN.findall(text)


def verify(text: str, board: chess.Board) -> VerificationResult:
    """Check a model response against the position before showing it."""
    violations = []

    for move in find_illegal_moves(text, board):
        violations.append(f"named an illegal move: {move}")

    if find_variation_lines(text):
        violations.append("calculated a variation")

    return VerificationResult(ok=not violations, violations=violations)
