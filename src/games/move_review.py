"""What went wrong on each of a player's moves, from engine evaluations.

A mistake is a move that cuts the player's winning chances by at least
MISTAKE points (Lichess's "mistake" line). Each mistake gets one kind, the
first that fits:

- MISSED_THREAT: the opponent already threatened something (if the player
  could pass, the opponent's best move would gain at least MISTAKE points
  and win material or mate), the player's move didn't stop it, and the
  opponent's best reply is that same move. Heisman's "hope chess": the
  threat was there to see.
- ALLOWED_TACTIC: the move hands the opponent material (counted from
  before the move) or a mate.
- MISSED_TACTIC: the best move won material or mated, and the player
  played something else.
- QUIET: none of the above - a positional or slow loss, or a tactic too
  deep for these checks.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import chess

from src.coach.line_facts import material_balance
from src.coach.prompts import game_phase
from src.games.game import Game
from src.games.win_chances import Eval, win_percent

MISTAKE = 10.0  # winning-chance points
BLUNDER = 15.0

MISSED_THREAT = "missed_threat"
ALLOWED_TACTIC = "allowed_tactic"
MISSED_TACTIC = "missed_tactic"
QUIET = "quiet"

# Club tactics are short: two moves each, then any captures or checks still
# pending. Longer windows counted pawns won by slow play as tactics.
TACTIC_PLIES = 4
# A pawn is enough: a threat to take a loose pawn is still a threat to see.
MATERIAL_SWING = 1


@dataclass(frozen=True)
class MoveRecord:
    ply: int
    san: str
    best_san: Optional[str]
    fen: str  # before the move
    phase: str
    before: float  # player's winning chances with the best move
    after: float  # and after the move played
    seconds_left: Optional[float]
    seconds_spent: Optional[float]
    low_clock: bool
    kind: Optional[str]  # None unless the move is a mistake

    @property
    def drop(self) -> float:
        return self.before - self.after

    @property
    def is_blunder(self) -> bool:
        return self.drop >= BLUNDER


@dataclass(frozen=True)
class ReviewedGame:
    game: Game
    records: List[MoveRecord]
    evals: List[Eval]  # one per position
    threats: Dict[int, Eval] = field(default_factory=dict)  # by ply, at mistakes

    def mistakes(self) -> List[MoveRecord]:
        return [r for r in self.records if r.kind is not None]


def is_low_clock(seconds_left: Optional[float], initial: Optional[int]) -> bool:
    if seconds_left is None or initial is None:
        return False
    return seconds_left < max(30.0, initial / 10)


def candidate_plies(game: Game, evals: Sequence[Eval]) -> List[int]:
    """The player's mistakes, which each need the threat check before they
    can be told apart."""
    _check_lengths(game, evals)
    return [ply for ply in game.my_plies() if _drop(game, evals, ply) >= MISTAKE]


def review_game(game: Game, evals: Sequence[Eval], threats: Dict[int, Eval]) -> List[MoveRecord]:
    """`evals` has one entry per position (one more than there are moves).
    `threats` holds, for each candidate ply where the player wasn't in check,
    the evaluation with the opponent to move instead: what they threatened."""
    _check_lengths(game, evals)
    boards = game.boards()
    records = []
    for ply in game.my_plies():
        board = boards[ply]
        drop = _drop(game, evals, ply)
        kind = None
        if drop >= MISTAKE:
            threat = None if board.is_check() else threats[ply]
            kind = _kind(board, game.moves[ply], evals[ply], evals[ply + 1], threat, game.color)
        left = game.seconds_left_before(ply)
        records.append(MoveRecord(
            ply=ply,
            san=game.moves[ply],
            best_san=_san(board, evals[ply].pv[:1]),
            fen=board.fen(),
            phase=game_phase(board),
            before=win_percent(evals[ply], game.color),
            after=win_percent(evals[ply + 1], game.color),
            seconds_left=left,
            seconds_spent=game.seconds_spent(ply),
            low_clock=is_low_clock(left, game.initial),
            kind=kind,
        ))
    return records


def _check_lengths(game: Game, evals: Sequence[Eval]) -> None:
    if len(evals) != len(game.moves) + 1:
        raise ValueError(f"game {game.id}: {len(evals)} evals for {len(game.moves) + 1} positions")


def _drop(game: Game, evals: Sequence[Eval], ply: int) -> float:
    return win_percent(evals[ply], game.color) - win_percent(evals[ply + 1], game.color)


def _kind(board: chess.Board, san: str, before: Eval, after: Eval,
          threat: Optional[Eval], me: chess.Color) -> str:
    if (threat is not None and threat.pv and after.pv[:1] == threat.pv[:1]
            and win_percent(before, me) - win_percent(threat, me) >= MISTAKE
            and _wins_something(board, threat, not me)):
        return MISSED_THREAT

    played = board.copy()
    played.push_san(san)
    if mates_for(after, not me) or material_gain(board, played, after.pv, not me) >= MATERIAL_SWING:
        return ALLOWED_TACTIC

    best = before.pv[:1]
    if best and best[0] != board.parse_san(san).uci() and (
            mates_for(before, me) or material_gain(board, board, before.pv, me) >= MATERIAL_SWING):
        return MISSED_TACTIC

    return QUIET


def _wins_something(board: chess.Board, threat: Eval, opponent: chess.Color) -> bool:
    """Whether the threat is concrete: material or a mate, not just a strong
    move such as a pawn push."""
    passed = board.copy()
    passed.push(chess.Move.null())
    return mates_for(threat, opponent) or material_gain(board, passed, threat.pv, opponent) >= MATERIAL_SWING


def mates_for(evaluation: Eval, side: chess.Color) -> bool:
    if evaluation.mate is None:
        return False
    return (evaluation.mate > 0) == (side == chess.WHITE)


def tactic_line(board: chess.Board, line: Sequence[str]) -> List[chess.Move]:
    """The start of an engine line that settles a tactic: a few moves, then
    any captures or checks still pending."""
    board = board.copy()
    moves = []
    for index, uci in enumerate(line):
        move = chess.Move.from_uci(uci)
        if index >= TACTIC_PLIES and not (board.is_capture(move) or board.gives_check(move)):
            break
        if move not in board.legal_moves:
            raise ValueError(f"engine line {' '.join(line)} has illegal {uci} in {board.fen()}")
        board.push(move)
        moves.append(move)
    return moves


def material_gain(start: chess.Board, board: chess.Board, line: Sequence[str], side: chess.Color) -> int:
    """Material `side` has gained since `start` once the tactic in `line`,
    played from `board`, is settled."""
    end = board.copy()
    for move in tactic_line(board, line):
        end.push(move)
    sign = 1 if side == chess.WHITE else -1
    return sign * (material_balance(end) - material_balance(start))


def _san(board: chess.Board, line: Sequence[str]) -> Optional[str]:
    return board.san(chess.Move.from_uci(line[0])) if line else None
