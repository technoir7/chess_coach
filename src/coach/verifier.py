"""Checks coach output against the position it claims to describe.

The prompts ask the model not to invent moves or calculate variations, but a
prompt is a request, not a guarantee - small local models comply most of the
time and not always. This module is the guarantee: anything the model says
about a move is checked against the legal move list before it reaches the user.

Quoting the engine is not calculating. When the engine's own principal
variations are supplied as `sanctioned_lines`, the coach may repeat them
verbatim - but only verbatim: a sequence that reorders, extends or splices
those lines is an invention wearing their clothes, and is rejected.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import chess

from src.coach import line_facts

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


def find_illegal_moves(
    text: str,
    board: chess.Board,
    sanctioned_lines: Optional[Sequence[Sequence[str]]] = None,
) -> List[str]:
    """Distinct moves named in `text` that the position cannot justify.

    A move is justified if it is available now to either side, or if it appears
    in a line the engine actually searched. Deduplicated: a move repeated four
    times is one invention, not four.
    """
    claimable = {_normalise(san) for san in _claimable_san(board)}
    for line in sanctioned_lines or []:
        claimable |= {_normalise(san) for san in line}

    illegal = []
    for match in _MOVE_PATTERN.finditer(text):
        claimed = match.group(0)
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


# "check" attributed to a specific move, e.g. "Bb5+ gives check" or "Nf3, check".
_CHECK_CLAIM = re.compile(
    rf"\b({_MOVE})[+#]?[^.;\n]{{0,40}}?\b(?:is|gives|delivers|with|,)\s*(?:a\s+)?check\b",
    re.IGNORECASE,
)

# A claimed exchange of a named piece: "exchange of queens", "trading rooks".
_EXCHANGE_CLAIM = re.compile(
    r"\b(?:exchange|exchanges|exchanged|trade|trades|traded|trading|swap|swapped)\b"
    r"[^.;\n]{0,30}?\b(queen|rook|bishop|knight|pawn)s?\b",
    re.IGNORECASE,
)
_EXCHANGE_CLAIM_REVERSED = re.compile(
    r"\b(queen|rook|bishop|knight|pawn)s?\b[^.;\n]{0,20}?"
    r"\b(?:are|is|get|gets|being)?\s*"
    r"(?:exchange|exchanges|exchanged|trade|trades|traded|trading|swap|swapped)\b",
    re.IGNORECASE,
)


def _line_facts(board: chess.Board, sanctioned_lines: Sequence[Sequence[str]]):
    return [line_facts.describe(board, line) for line in sanctioned_lines]


def find_false_check_claims(
    text: str,
    board: chess.Board,
    sanctioned_lines: Optional[Sequence[Sequence[str]]] = None,
) -> List[str]:
    """Moves the text calls a check that do not give check anywhere.

    Whether a move is check is settled by the board, so a wrong claim is a
    plain falsehood rather than a matter of interpretation.
    """
    checking = set()
    for facts in _line_facts(board, sanctioned_lines or []):
        checking |= {_normalise(san) for san in facts.checking_moves()}

    # A move that gives check from the current position counts too.
    for move in board.legal_moves:
        replay = board.copy()
        san = replay.san(move)
        replay.push(move)
        if replay.is_check():
            checking.add(_normalise(san))

    false_claims = []
    for match in _CHECK_CLAIM.finditer(text):
        claimed = _normalise(match.group(1))
        if claimed not in checking and claimed not in false_claims:
            false_claims.append(claimed)
    return false_claims


def find_false_exchange_claims(
    text: str,
    board: chess.Board,
    sanctioned_lines: Optional[Sequence[Sequence[str]]] = None,
) -> List[str]:
    """Piece types the text says are traded but which nothing ever captures.

    The coach said a line "leads to exchanges of Queens" in a line where the
    black queen simply moved about and no queen was ever taken.
    """
    exchanged = set()
    for facts in _line_facts(board, sanctioned_lines or []):
        exchanged |= facts.captured_types

    claimed = set()
    for pattern in (_EXCHANGE_CLAIM, _EXCHANGE_CLAIM_REVERSED):
        for match in pattern.finditer(text):
            claimed.add(match.group(1).lower())

    return sorted(claimed - exchanged)


# "Bb5+, attacking the Black Bishop" - a move said to bear on a named piece.
_ATTACK_CLAIM = re.compile(
    rf"\b({_MOVE})[+#]?[^.;\n]{{0,40}}?\battack(?:s|ing|ed)?\b[^.;\n]{{0,25}}?"
    r"\b(king|queen|rook|bishop|knight|pawn)\b",
    re.IGNORECASE,
)


def find_false_attack_claims(
    text: str,
    board: chess.Board,
    sanctioned_lines: Optional[Sequence[Sequence[str]]] = None,
) -> List[str]:
    """Moves said to attack a piece type they do not bear on.

    What a piece attacks from a square is fixed by the rules, so this settles
    claims like "Bb5+, attacking the Black Bishop" - that move gives check, so
    it attacks the king and nothing else of note.
    """
    attacks_by_move = {}
    for facts in _line_facts(board, sanctioned_lines or []):
        for fact in facts.moves:
            attacks_by_move.setdefault(_normalise(fact.san), set()).update(fact.attacks)

    # Moves available right now count too, played from the current position.
    for move in board.legal_moves:
        replay = board.copy()
        san = _normalise(replay.san(move))
        replay.push(move)
        targets = set()
        for square in replay.attacks(move.to_square):
            piece = replay.piece_at(square)
            if piece is not None and piece.color != (not replay.turn):
                targets.add(chess.piece_name(piece.piece_type))
        attacks_by_move.setdefault(san, set()).update(targets)

    false_claims = []
    for match in _ATTACK_CLAIM.finditer(text):
        claimed_move = _normalise(match.group(1))
        claimed_target = match.group(2).lower()

        known = attacks_by_move.get(claimed_move)
        if known is None:
            continue  # not a move we can place; the move checks catch inventions

        entry = f"{claimed_move} does not attack a {claimed_target}"
        if claimed_target not in known and entry not in false_claims:
            false_claims.append(entry)
    return false_claims


def verify(
    text: str,
    board: chess.Board,
    sanctioned_lines: Optional[Sequence[Sequence[str]]] = None,
) -> VerificationResult:
    """Check a model response against the position before showing it."""
    violations = []

    for move in find_illegal_moves(text, board, sanctioned_lines):
        violations.append(f"named an illegal move: {move}")

    for line in find_unsanctioned_lines(text, sanctioned_lines):
        violations.append(f"gave a line the engine did not search: {line}")

    for move in find_false_check_claims(text, board, sanctioned_lines):
        violations.append(f"called a move a check when it is not: {move}")

    for piece in find_false_exchange_claims(text, board, sanctioned_lines):
        violations.append(f"claimed an exchange of {piece}s that never happens")

    for claim in find_false_attack_claims(text, board, sanctioned_lines):
        violations.append(claim)

    return VerificationResult(ok=not violations, violations=violations)
