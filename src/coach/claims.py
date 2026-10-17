"""Checks the factual claims an explanation makes, one by one, against the board.

The self-check in round 5 left mistakes that are chess clichés: "castles and
connects the rooks" with a bishop still between them, "the pinned pawn can't
move" while it could still push. They read as true, so the model checking its
own draft let them through, and nothing in the facts it was given contradicted
them outright.

So the model also lists the claims its answer makes, in a fixed form, and this
module decides each one from the board. Copying out a claim is a much easier
job than judging it, and the board cannot be talked into a cliché.

A claim is a dict: {"sentence": 3, "at": "current" or {"line": "<first move of
an engine line>", "after": "16... Rc8"}, "kind": ..., "args": {...}, "holds":
true or false}. A claim that cannot be read - an unknown kind, a position that
cannot be found - is left unchecked rather than guessed at.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

import chess

from src.coach import relations, structure
from src.coach.line_facts import material_balance


@dataclass
class Finding:
    sentence: int
    claim: dict
    truth: str


@dataclass
class Result:
    false: List[Finding] = field(default_factory=list)
    unchecked: List[dict] = field(default_factory=list)


class _Unreadable(Exception):
    pass


class _NoPiece(Exception):
    pass


def _bare(san: str) -> str:
    return str(san).strip().rstrip("+#!?")


_AFTER = re.compile(r"^(?:(\d+)\s*(\.\.\.|\.)\s*)?(\S+)$")


def _position(board: chess.Board, lines: Sequence[Sequence[str]], at) -> chess.Board:
    """The board a claim is about: now, or just after a move inside an engine line."""
    if at == "current":
        return board
    if not isinstance(at, dict):
        raise _Unreadable(f"position {at!r}")
    line = next((l for l in lines if l and _bare(l[0]) == _bare(at.get("line", ""))), None)
    want = _AFTER.match(str(at.get("after", "")).strip())
    if line is None or want is None:
        raise _Unreadable(f"position {at!r}")
    number, dots, san = want.groups()

    replay, matches = board.copy(), []
    for move_san in line:
        try:
            move = replay.parse_san(move_san)
        except ValueError:
            break
        here = (replay.fullmove_number, replay.turn == chess.WHITE)
        replay.push(move)
        if _bare(move_san) == _bare(san) and (number is None or here == (int(number), dots == ".")):
            matches.append(replay.copy())
    if len(matches) != 1:
        raise _Unreadable(f"position {at!r}")
    return matches[0]


def _square(args: Dict, key: str) -> int:
    try:
        return chess.parse_square(str(args[key]).strip().lower())
    except (KeyError, ValueError):
        raise _Unreadable(f"{key} in {args!r}")


def _color(args: Dict) -> chess.Color:
    side = str(args.get("side", "")).strip().lower()
    if side not in ("white", "black"):
        raise _Unreadable(f"side in {args!r}")
    return side == "white"


def _side(color: chess.Color) -> str:
    return "White" if color == chess.WHITE else "Black"


def _name(board: chess.Board, square: int) -> str:
    piece = board.piece_at(square)
    return f"{chess.piece_name(piece.piece_type).capitalize()} on {chess.square_name(square)}"


def _piece(board: chess.Board, square: int) -> chess.Piece:
    piece = board.piece_at(square)
    if piece is None:
        raise _NoPiece(square)
    return piece


def _attacks(board, args) -> Tuple[bool, str]:
    square, target = _square(args, "piece"), _square(args, "target")
    piece, other = _piece(board, square), board.piece_at(target)
    actual = target in board.attacks(square) and (other is None or other.color != piece.color)
    return actual, relations.piece(board, square)


def _defends(board, args) -> Tuple[bool, str]:
    square, target = _square(args, "piece"), _square(args, "target")
    piece, other = _piece(board, square), _piece(board, target)
    actual = other.color == piece.color and target in board.attacks(square)
    return actual, relations.piece(board, square)


def _defended(board, args) -> Tuple[bool, str]:
    square = _square(args, "square")
    piece = _piece(board, square)
    defenders = [_name(board, s) for s in board.attackers(piece.color, square)]
    return bool(defenders), f"the {_name(board, square)} is defended by {', '.join(defenders) or 'nothing'}"


def _pinned(board, args) -> Tuple[bool, str]:
    square = _square(args, "square")
    _piece(board, square)
    pins = [(a, b) for a, pinned, b in relations.pins(board) if pinned == square]
    if not pins:
        return False, f"nothing pins the {_name(board, square)}"
    pinner, behind = pins[0]
    return True, f"the {_name(board, pinner)} pins the {_name(board, square)} to the {_name(board, behind)}"


def _can_move(board, args) -> Tuple[bool, str]:
    square = _square(args, "square")
    piece = _piece(board, square)
    turn = board.copy(stack=False)
    turn.turn = piece.color
    moves = [turn.san(m) for m in turn.legal_moves if m.from_square == square]
    return bool(moves), f"the {_name(board, square)} has legal moves: {', '.join(moves) or 'none'}"


def _forced(board, args) -> Tuple[bool, str]:
    moves = [board.san(m) for m in board.legal_moves]
    return len(moves) == 1, f"{_side(board.turn)} has {len(moves)} legal moves here"


def _check(board, args) -> Tuple[bool, str]:
    for side in (board.turn, not board.turn):
        turn = board.copy(stack=False)
        turn.turn = side
        try:
            move = turn.parse_san(str(args.get("move", "")))
        except ValueError:
            continue
        actual = turn.gives_check(move)
        return actual, f"{turn.san(move)} {'gives' if actual else 'does not give'} check here"
    raise _Unreadable(f"move in {args!r}")


def _connected_rooks(board, args) -> Tuple[bool, str]:
    color = _color(args)
    rooks = sorted(board.pieces(chess.ROOK, color))
    if len(rooks) != 2:
        return False, f"{_side(color)} has {len(rooks)} rook(s)"
    a, b = rooks
    if chess.square_rank(a) != chess.square_rank(b) and chess.square_file(a) != chess.square_file(b):
        return False, f"{_side(color)}'s rooks on {chess.square_name(a)} and {chess.square_name(b)} share no rank or file"
    between = [_name(board, s) for s in chess.SquareSet(chess.between(a, b)) if board.piece_at(s)]
    if between:
        return False, f"{', '.join(between)} stand between {_side(color)}'s rooks"
    return True, f"nothing stands between {_side(color)}'s rooks"


_MINOR_HOMES = {
    chess.WHITE: {chess.B1: chess.KNIGHT, chess.G1: chess.KNIGHT, chess.C1: chess.BISHOP, chess.F1: chess.BISHOP},
    chess.BLACK: {chess.B8: chess.KNIGHT, chess.G8: chess.KNIGHT, chess.C8: chess.BISHOP, chess.F8: chess.BISHOP},
}


def _developed(board, args) -> Tuple[bool, str]:
    color = _color(args)
    home = [
        _name(board, sq) for sq, kind in sorted(_MINOR_HOMES[color].items())
        if board.piece_at(sq) == chess.Piece(kind, color)
    ]
    return not home, f"{_side(color)} minor pieces still on their starting squares: {', '.join(home) or 'none'}"


def _piece_on(board, args) -> Tuple[bool, str]:
    square, color = _square(args, "square"), _color(args)
    piece = board.piece_at(square)
    actual = (
        piece is not None and piece.color == color
        and chess.piece_name(piece.piece_type) == str(args.get("piece", "")).strip().lower()
    )
    there = f"a {_side(piece.color)} {_name(board, square)}" if piece else "nothing"
    return actual, f"on {chess.square_name(square)} stands {there}"


def _material(board, args) -> Tuple[bool, str]:
    balance = material_balance(board)
    leader = "level" if balance == 0 else _side(balance > 0)
    said = str(args.get("leader", "")).strip().lower()
    if said not in ("white", "black", "level"):
        raise _Unreadable(f"leader in {args!r}")
    detail = "material is level" if balance == 0 else f"{leader} is {abs(balance)} pawn(s) ahead"
    return said == leader.lower(), detail


def _pawn(board, args) -> Tuple[bool, str]:
    square, kind = _square(args, "square"), str(args.get("kind", "")).strip().lower()
    if kind not in ("doubled", "isolated", "passed"):
        raise _Unreadable(f"kind in {args!r}")
    piece = _piece(board, square)
    if piece.piece_type != chess.PAWN:
        return False, f"the {_name(board, square)} is not a pawn"
    kinds = structure.pawn_kinds(board, square)
    return kind in kinds, f"the pawn on {chess.square_name(square)} is {', '.join(sorted(kinds)) or 'not doubled, isolated or passed'}"


def _open_file(board, args) -> Tuple[bool, str]:
    name = str(args.get("file", "")).strip().lower()
    if name not in chess.FILE_NAMES:
        raise _Unreadable(f"file in {args!r}")
    pawns = [_name(board, s) for s in board.pieces(chess.PAWN, chess.WHITE) | board.pieces(chess.PAWN, chess.BLACK)
             if chess.square_file(s) == chess.FILE_NAMES.index(name)]
    return not pawns, f"the {name}-file holds {', '.join(pawns) or 'no pawns'}"


KINDS = {
    "attacks": _attacks,
    "defends": _defends,
    "defended": _defended,
    "pinned": _pinned,
    "can_move": _can_move,
    "forced": _forced,
    "check": _check,
    "connected_rooks": _connected_rooks,
    "all_minor_pieces_developed": _developed,
    "piece_on": _piece_on,
    "material": _material,
    "pawn": _pawn,
    "open_file": _open_file,
}


def _where(at) -> str:
    if at == "current":
        return "in the current position"
    return f"after {at.get('after')} in the {at.get('line')} line"


def check(board: chess.Board, lines: Sequence[Sequence[str]], claims: List[dict]) -> Result:
    result = Result()
    for claim in claims:
        try:
            if not isinstance(claim, dict) or claim.get("kind") not in KINDS:
                raise _Unreadable(f"kind {claim!r}")
            sentence = int(claim["sentence"])
            position = _position(board, lines, claim.get("at", "current"))
            holds = claim.get("holds", True) is not False
            args = claim.get("args") or {}
            try:
                actual, detail = KINDS[claim["kind"]](position, args)
            except _NoPiece as e:
                actual, detail = not holds, f"there is no piece on {chess.square_name(e.args[0])}"
        except (_Unreadable, KeyError, TypeError, ValueError):
            result.unchecked.append(claim)
            continue
        if actual != holds:
            result.false.append(Finding(sentence, claim, f"{_where(claim.get('at', 'current'))}, {detail}"))
    return result
