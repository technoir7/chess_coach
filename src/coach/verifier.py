"""Checks coach output against the position it claims to describe.

The prompts ask the model not to invent moves or calculate variations, but a
prompt is a request, not a guarantee - small local models comply most of the
time and not always. This module is the guarantee: anything the model says
about a move is checked against the legal move list before it reaches the user.

Only claims made of moves are judged here: which moves are named, and which
sequences. Patterns that read checks, attacks and trades out of prose were
dropped after round 6 of the eval (evals/README.md): once the model checked
its own draft against the facts, they rejected 20 correct answers in three
rounds and caught no wrong one.

Quoting the engine is not calculating. When the engine's own principal
variations are supplied as `sanctioned_lines`, the coach may repeat them
verbatim - but only verbatim: a sequence that reorders, extends or splices
those lines is an invention wearing their clothes, and is rejected.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import chess


# Piece moves, pawn captures and castling are unambiguous claims about a move.
#
# Bare pawn pushes ("e4") are deliberately NOT matched: they are spelled exactly
# like a square reference, and "the pawn on e4" is ordinary description rather
# than a claimed move. Matching them would reject correct prose constantly, so
# this trades a little recall for precision it can rely on.
_MOVE = (
    r"O-O-O|O-O|0-0-0|0-0"                           # castling
    r"|[KQRBN][a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?"  # piece moves
    r"|[a-h]x[a-h][1-8](?:=[QRBN])?"                 # pawn captures
)
_MOVE_PATTERN = re.compile(rf"\b({_MOVE})[+#]?")

# Inside a quoted line, a bare pawn push IS unambiguous - it sits in a run of
# other moves rather than in prose - so runs match a wider token set.
_LINE_MOVE_PATTERN = re.compile(rf"\b({_MOVE}|[a-h][1-8](?:=[QRBN])?)[+#]?")

# What may sit between two moves of the same line: whitespace and move numbers
# ("2." or "2...") and nothing else. A comma or a word ends the run, which is
# what separates a played sequence from a list of candidate moves.
_RUN_GAP = re.compile(r"^[\s]*(?:\d+\s*\.(?:\s*\.\.)?[\s]*)?$")


@dataclass
class VerificationResult:
    ok: bool
    violations: List[str] = field(default_factory=list)


def _normalise(san: str) -> str:
    """Drop check/mate marks so notation differences are not treated as lies."""
    return san.rstrip("+#").replace("0", "O")


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


def _game_so_far(board: chess.Board) -> List[str]:
    """The moves played to reach `board`, in SAN. Retelling them is not
    calculating: "After 1. e4 e5" was rejected as an unsearched line."""
    replay, played = board.root(), []
    for move in board.move_stack:
        played.append(replay.san(move))
        replay.push(move)
    return played


def find_move_runs(text: str) -> List[List[str]]:
    """Sequences of moves played one after another, as the model wrote them.

    Moves joined only by whitespace and move numbers form a line; anything else
    between them (a comma, a word) means they are being listed, not played.
    """
    tokens = [(m.group(0), m.start(), m.end()) for m in _LINE_MOVE_PATTERN.finditer(text)]

    runs, current = [], []
    for index, (token, start, end) in enumerate(tokens):
        if not current:
            current = [token]
        else:
            gap = text[tokens[index - 1][2]:start]
            if _RUN_GAP.match(gap):
                current.append(token)
            else:
                if len(current) > 1:
                    runs.append(current)
                current = [token]

    if len(current) > 1:
        runs.append(current)
    return runs


def _is_quoted_from(run: Sequence[str], sanctioned_lines: Sequence[Sequence[str]]) -> bool:
    """Whether `run` appears contiguously, in order, inside a searched line."""
    normalised = [_normalise(m) for m in run]
    for line in sanctioned_lines:
        moves = [_normalise(m) for m in line]
        for start in range(len(moves) - len(normalised) + 1):
            if moves[start:start + len(normalised)] == normalised:
                return True
    return False


def _names_a_standing_piece(token: str, boards: Sequence[chess.Board]) -> bool:
    """Whether `token` names a piece where it stands ("White's Nf3"), now or at
    some point in a searched line.

    Prose names pieces in move notation - "supported by Nc3, Nf3 and Bd3" - and
    a piece cannot move to a square it occupies, so such a token is a reference
    rather than a claimed move. A capture always moves, so it never qualifies.
    The prompt describes where each line leaves the pieces, and answers name
    them there: round 9's "the queen attacks ... the Rf8", a rook that reaches
    f8 by castling in the line, was rejected.
    """
    token = token.rstrip("+#")
    if token[0] not in "KQRBN" or "x" in token:
        return False
    square = chess.parse_square(token[-2:])
    return any(
        (piece := board.piece_at(square)) is not None and piece.symbol().upper() == token[0]
        for board in boards
    )


def _positions(board: chess.Board, lines: Sequence[Sequence[str]]) -> List[chess.Board]:
    """The board now and after each move of each line, as far as it plays."""
    positions = [board]
    for line in lines:
        replay = board.copy()
        for san in line:
            try:
                replay.push_san(san)
            except ValueError:
                break
            positions.append(replay.copy(stack=False))
    return positions


def find_illegal_moves(
    text: str,
    board: chess.Board,
    sanctioned_lines: Optional[Sequence[Sequence[str]]] = None,
) -> List[str]:
    """Distinct moves named in `text` that the position cannot justify.

    A move is justified if it is available now to either side, or if it
    appears in a line the engine actually searched. Deduplicated: a move
    repeated four times is one invention, not four.
    """
    claimable = {_normalise(san) for san in _claimable_san(board)}
    for line in [*(sanctioned_lines or []), _game_so_far(board)]:
        claimable |= {_normalise(san) for san in line}

    positions = _positions(board, sanctioned_lines or [])
    illegal = []
    for match in _MOVE_PATTERN.finditer(text):
        claimed = match.group(0)
        if _names_a_standing_piece(claimed, positions):
            continue
        if _normalise(claimed) not in claimable and claimed not in illegal:
            illegal.append(claimed)
    return illegal


def find_unsanctioned_lines(
    text: str,
    sanctioned_lines: Optional[Sequence[Sequence[str]]] = None,
) -> List[str]:
    """Move sequences that are not verbatim quotations of a searched line.

    With no sanctioned lines supplied, any sequence at all is unsanctioned -
    the coach has no verified continuation to quote, so producing one means it
    calculated.
    """
    unsanctioned = []
    for run in find_move_runs(text):
        if not _is_quoted_from(run, sanctioned_lines or []):
            unsanctioned.append(" ".join(run))
    return unsanctioned


def verify(
    text: str,
    board: chess.Board,
    sanctioned_lines: Optional[Sequence[Sequence[str]]] = None,
) -> VerificationResult:
    """Check a model response against the position before showing it."""
    violations = []

    for move in find_illegal_moves(text, board, sanctioned_lines):
        violations.append(f"named an illegal move: {move}")

    # Each side's own moves are quotable too: "White has played 1.e4 2.c4
    # 3.Nc3" lists the game truthfully while skipping Black's replies.
    game = _game_so_far(board)
    quotable = [*(sanctioned_lines or []), game, game[0::2], game[1::2]]
    for line in find_unsanctioned_lines(text, quotable):
        violations.append(f"gave a line the engine did not search: {line}")

    return VerificationResult(ok=not violations, violations=violations)
