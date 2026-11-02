"""Flashcards from a player's own mistakes.

Only the mistakes a card can teach: tactical ones made with time on the
clock. Quiet mistakes have no single answer to recall, and low-clock ones
are a clock problem. Most cards are defensive, since in the games this was
built from, half of all mistakes came from not checking the opponent's reply.
"""

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import chess

from src.coach.line_facts import material_balance, points
from src.games.move_review import (ALLOWED_TACTIC, BLUNDER, MISSED_TACTIC, MISSED_THREAT,
                                   MoveRecord, ReviewedGame, material_gain, mates_for, tactic_line)
from src.games.report import WINNING
from src.games.win_chances import Eval, win_percent

CARD_KINDS = (MISSED_THREAT, ALLOWED_TACTIC, MISSED_TACTIC)
# "Find the best move" needs one clear answer: the runner-up must be this
# many points of winning chances worse, or the card would mark a good move wrong.
STANDS_OUT = 15.0

THREAT, BEST, PLAYED = "threat", "best", "played"


@dataclass(frozen=True)
class Card:
    id: str
    kind: str
    fen: str  # the position on the front, the player to move
    orientation: chess.Color
    question: str
    shown_move: Optional[str]  # UCI, drawn on the front
    answer: Tuple[str, ...]  # lines of text
    arrows: Tuple[Tuple[str, str], ...]  # (UCI, role), drawn on the back
    line_fen: str  # where the answer's line starts: its first move is the one to find
    line: Tuple[str, ...]  # UCI, the line the answer shows
    tags: Tuple[str, ...]
    played_on: str  # the game's date, YYYY-MM-DD
    link: str


def select(reviewed: Sequence[ReviewedGame], per_game: int = 2,
           minimum_drop: float = BLUNDER) -> List[Tuple[ReviewedGame, MoveRecord]]:
    """The biggest teachable mistakes, at most `per_game` from each game, so
    the deck stays small enough to keep up with."""
    chosen = []
    for rg in reviewed:
        teachable = [r for r in rg.mistakes()
                     if r.kind in CARD_KINDS and not r.low_clock and r.drop >= minimum_drop]
        teachable.sort(key=lambda r: -r.drop)
        chosen.extend((rg, r) for r in sorted(teachable[:per_game], key=lambda r: r.ply))
    return chosen


def build_card(rg: ReviewedGame, record: MoveRecord, second_best: Optional[Eval] = None) -> Optional[Card]:
    """`second_best` is required for a missed tactic: the card is only made
    when the best move stands out from the rest."""
    game, ply = rg.game, record.ply
    board = chess.Board(record.fen)
    me = game.color
    played = board.parse_san(record.san)
    before, after = rg.evals[ply], rg.evals[ply + 1]
    best = chess.Move.from_uci(before.pv[0])
    side = "White" if me == chess.WHITE else "Black"
    chances = f"Your winning chances: {record.before:.0f}% with {_numbered(board, best)}, {record.after:.0f}% after {_numbered(board, played)}."
    after_board = board.copy()
    after_board.push(played)

    if record.kind == MISSED_THREAT:
        threat = rg.threats[ply]
        passed = board.copy()
        passed.push(chess.Move.null())
        question = f"{side} to move. What is your opponent threatening?"
        shown = None
        line_board, line = passed, card_line(board, passed, threat, not me)
        answer = (
            f"The threat: {passed.variation_san(line)}, {_wins(board, passed, threat, not me)}.",
            f"You played {_numbered(board, played)}.",
            _what_they_did(rg, ply, after_board, threat.pv[0]),
            f"Better: {_numbered(board, best)}.",
            chances,
        )
        arrows = ((threat.pv[0], THREAT), (best.uci(), BEST))

    elif record.kind == ALLOWED_TACTIC:
        question = f"{side} to move. You're about to play {_numbered(board, played)}. What does it allow?"
        shown = played.uci()
        line_board, line = after_board, card_line(board, after_board, after, not me)
        answer = (
            f"Their best reply: {after_board.variation_san(line)}, {_wins(board, after_board, after, not me)}.",
            _what_they_did(rg, ply, after_board, after.pv[0]),
            f"Better: {_numbered(board, best)}.",
            chances,
        )
        arrows = ((played.uci(), PLAYED), (after.pv[0], THREAT), (best.uci(), BEST))

    elif record.kind == MISSED_TACTIC:
        if second_best is None:
            raise ValueError(f"{game.id} ply {ply}: a tactic card needs the second-best move's eval")
        if win_percent(before, me) - win_percent(second_best, me) < STANDS_OUT:
            return None
        question = f"{side} to move. Find the best move."
        shown = None
        line_board, line = board, card_line(board, board, before, me)
        answer = (
            f"{board.variation_san(line)}, {_wins(board, board, before, me)}.",
            f"You played {_numbered(board, played)}.",
            chances,
        )
        arrows = ((best.uci(), BEST),)

    else:
        raise ValueError(f"no card for a {record.kind} mistake")

    tags = [record.kind, game.speed, record.phase.lower(), str(game.played_at.year)]
    if record.before >= WINNING:
        tags.append("thrown_win")
    return Card(
        id=f"{game.id}-{ply}", kind=record.kind, fen=board.fen(), orientation=me,
        question=question, shown_move=shown, answer=answer, arrows=arrows,
        line_fen=line_board.fen(), line=tuple(m.uci() for m in line),
        tags=tuple(tags), played_on=game.played_at.date().isoformat(), link=game.link(ply),
    )


def _numbered(board: chess.Board, move: chess.Move) -> str:
    return board.variation_san([move])


def shown_line(start: chess.Board, board: chess.Board, pv: Sequence[str], side: chess.Color) -> List[chess.Move]:
    """The engine line from `board`, cut at the first move where `side` has
    won all it will win (counted from `start`) and the next move doesn't take
    straight back on that square. A blunder then shows its capture, not the
    trades the engine plays out after it; a combination, whose material
    swings until the end, keeps every move."""
    moves = tactic_line(board, pv)
    replay, gains = board.copy(), []
    sign = 1 if side == chess.WHITE else -1
    for move in moves:
        replay.push(move)
        gains.append(sign * (material_balance(replay) - material_balance(start)))
    if not gains or gains[-1] <= 0:
        return moves
    for index, gain in enumerate(gains):
        last = index + 1 == len(moves)
        if gain == gains[-1] and (last or moves[index + 1].to_square != moves[index].to_square):
            return moves[:index + 1]
    return moves


def card_line(start: chess.Board, board: chess.Board, evaluation: Eval, side: chess.Color) -> List[chess.Move]:
    """The moves a card shows for `side`'s tactic: a mate in full, anything
    else cut where the material is won."""
    if mates_for(evaluation, side):
        return tactic_line(board, evaluation.pv)
    return shown_line(start, board, evaluation.pv, side)


def _what_they_did(rg: ReviewedGame, ply: int, after_board: chess.Board, best_reply: str) -> str:
    """The engine's best reply is what they could do; the game says what
    they did."""
    if ply + 1 >= len(rg.game.moves):
        return "The game ended there."
    reply = after_board.parse_san(rg.game.moves[ply + 1])
    if reply.uci() == best_reply:
        return "They played it."
    return f"They missed it and played {_numbered(after_board, reply)}."


def _wins(start: chess.Board, board: chess.Board, evaluation: Eval, side: chess.Color) -> str:
    """What the line wins, and where material then stands: "winning 9
    points" alone was true of a queen recaptured, and misleading."""
    if mates_for(evaluation, side):
        return "leading to mate"
    end = board.copy()
    for move in tactic_line(board, evaluation.pv):
        end.push(move)
    balance = material_balance(end)
    standing = ("material is level" if balance == 0
                else f"{'White' if balance > 0 else 'Black'} is {points(abs(balance))} ahead")
    gain = material_gain(start, board, evaluation.pv, side)
    won = f"winning {points(gain)} of material" if gain > 0 else "winning no material yet"
    return f"{won}; afterwards {standing}"
