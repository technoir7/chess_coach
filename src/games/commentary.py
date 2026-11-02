"""Commentary for the back of a card: why the threat, the mistake or the shot works.

The coach's general explanation was tried first and contradicted 2 of 2
cards about a threat ("neither side faces a threat"): it doesn't know what a
card teaches, and its threats are only pieces hanging now. So commentary gets
a brief built for the card - the card itself, the position's facts, each of
the card's lines played out move by move, and what the move played changed -
and is checked as the coach's explanations are: against the brief, then with
a board tool to hand, then by the move verifier. evals/cards/ measures it.
"""

from collections import Counter
import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

import chess

from src.coach import line_facts, prompts, relations, review, structure, threats, verifier, walkthrough
from src.games import cards
from src.games.cards import Card
from src.games.move_review import (ALLOWED_TACTIC, MISSED_TACTIC, MISSED_THREAT, MoveRecord,
                                   ReviewedGame, tactic_line)

# Bumped whenever the brief or instructions change, so cached commentary
# written from an older prompt is written again.
VERSION = 4

# As the coach's lines: deep enough to show what follows, short enough that
# three lines don't crowd out the rest. A tactic still pending runs on.
LINE_PLIES = 8


@dataclass(frozen=True)
class Brief:
    text: str
    kind: str
    fen: str  # the card's position
    threat_fen: Optional[str]  # the same, opponent to move: where the threat line starts
    lines: Tuple[Tuple[str, ...], ...]  # SAN: the only sequences commentary may quote


@dataclass(frozen=True)
class Commentary:
    draft: str
    text: str


def _side(color: chess.Color) -> str:
    return "White" if color == chess.WHITE else "Black"


def _name(board: chess.Board, square: int) -> str:
    piece = board.piece_at(square)
    return f"{chess.piece_name(piece.piece_type).capitalize()} on {chess.square_name(square)}"


def _names(board: chess.Board, squares) -> str:
    return ", ".join(_name(board, s) for s in sorted(squares)) or "nothing"


def _own_pieces(board: chess.Board, squares, color: chess.Color) -> set:
    return {s for s in squares
            if (p := board.piece_at(s)) is not None and p.color == color and p.piece_type != chess.KING}


def move_changes(board: chess.Board, move: chess.Move) -> List[str]:
    """What `move` did to the mover's own pieces: where the moved piece now
    stands guarded, what it stopped defending, and which pieces it left
    attacked. The board says this outright; a mistake is usually one of them."""
    me = board.turn
    after = board.copy()
    after.push(move)
    to = move.to_square
    facts = [f"{_side(me)} {_name(after, to)} is attacked by {_names(after, after.attackers(not me, to))} "
             f"and defended by {_names(after, after.attackers(me, to))}"]

    stopped = (_own_pieces(board, board.attacks(move.from_square), me)
               - _own_pieces(after, after.attacks(to), me) - {to})
    facts += [f"it no longer defends {_name(board, s)}" for s in sorted(stopped)]

    for square in sorted(_own_pieces(after, chess.SQUARES, me) - {to}):
        attackers = after.attackers(not me, square)
        if not attackers:
            continue
        defenders = after.attackers(me, square)
        if not board.attackers(not me, square):
            facts.append(f"{_side(me)} {_name(after, square)} is now attacked by {_names(after, attackers)}; "
                         f"defended by {_names(after, defenders)}")
        elif board.attackers(me, square) - defenders - {move.from_square} or (
                move.from_square in board.attackers(me, square) and to not in defenders):
            facts.append(f"{_side(me)} {_name(after, square)} was defended by "
                         f"{_names(board, board.attackers(me, square))} and is now defended by "
                         f"{_names(after, defenders)}, attacked by {_names(after, attackers)}")
    return facts


def escapes(board: chess.Board, square: int) -> List[str]:
    """Where each piece attacked by the piece on `square` can go, and what
    covers each square once it is there. `board` is just after the attacking
    move, the attacked side to move. "Trapped" and "can't save both" are
    claims about these squares, so the brief states them."""
    if board.is_check():
        # Nothing can move away while the king is in check; listing pieces
        # with "nowhere to go" then read as trapped (round 1, card c32).
        return []
    attacker = board.piece_at(square).color
    facts = []
    for target in sorted(board.attacks(square)):
        piece = board.piece_at(target)
        if piece is None or piece.color == attacker or piece.piece_type == chess.KING:
            continue
        options = []
        for move in board.legal_moves:
            if move.from_square != target:
                continue
            capture, check = board.is_capture(move), board.gives_check(move)
            after = board.copy()
            after.push(move)
            covering = after.attackers(attacker, move.to_square)
            # Not "safe": round 2 wrote "its only safe retreat" of a square
            # where the bishop was trapped two moves later.
            options.append(f"{'x' if capture else ''}{chess.square_name(move.to_square)}{'+' if check else ''} "
                           f"({'covered by ' + _names(after, covering) if covering else 'not attacked there'})")
        facts.append(f"{_side(piece.color)} {_name(board, target)} can go to: "
                     + (", ".join(options) if options else "nowhere (no legal moves)"))
    return facts


def overloaded(board: chess.Board, color: chess.Color) -> List[str]:
    """Pieces of `color` that are the only defender of two or more attacked
    pieces: a defender that can't do both jobs. Round 2's commentary missed
    this when it was the reason material fell."""
    sole = {}
    for square in _own_pieces(board, chess.SQUARES, color):
        defenders = board.attackers(color, square)
        if board.attackers(not color, square) and len(defenders) == 1:
            sole.setdefault(next(iter(defenders)), []).append(square)
    return [f"{_side(color)} {_name(board, d)} is the only defender of {_names(board, guarded)}"
            for d, guarded in sorted(sole.items()) if len(guarded) >= 2]


def events(board: chess.Board, move: chess.Move) -> List[str]:
    """The tactical idea in a move, read off the board: checks (discovered or
    double), pins it creates, and double attacks by the moved piece. Round 1's
    commentary missed exactly these when the brief left them to be spotted."""
    after = board.copy()
    after.push(move)
    mover = board.turn
    moved = move.to_square
    found = []
    if after.is_check():
        checkers = sorted(after.checkers(), key=lambda s: s != moved)
        if len(checkers) > 1:
            found.append("double check by " + " and ".join(_name(after, s) for s in checkers))
        elif checkers[0] != moved and not board.is_castling(move):
            found.append(f"discovered check by {_name(after, checkers[0])}")
    for pinner, pinned, behind in sorted(set(relations.pins(after)) - set(relations.pins(board))):
        found.append(f"{_name(after, pinner)} pins {_name(after, pinned)} to {_name(after, behind)}")
    value = line_facts.PIECE_VALUES.get(after.piece_at(moved).piece_type, 100)
    targets = [s for s in after.attacks(moved)
               if (p := after.piece_at(s)) is not None and p.color != mover
               and (p.piece_type == chess.KING or not after.attackers(not mover, s)
                    or line_facts.PIECE_VALUES[p.piece_type] > value)]
    if len(targets) >= 2:
        targets.sort(key=lambda s: -line_facts.PIECE_VALUES.get(after.piece_at(s).piece_type, 100))
        found.append(f"double attack: {_name(after, moved)} attacks " + ", ".join(_name(after, s) for s in targets))
    return found


def net_material(board: chess.Board, moves: Sequence[chess.Move]) -> str:
    """Who loses what over a line, with even trades cancelled. Round 1 read
    "Qxa5, Rxd1+, Kxd1" as a queen for a rook."""
    lost = {chess.WHITE: Counter(), chess.BLACK: Counter()}
    replay = board.copy()
    for move in moves:
        if replay.is_capture(move):
            square = move.to_square if not replay.is_en_passant(move) else \
                chess.square(chess.square_file(move.to_square), chess.square_rank(move.from_square))
            lost[not replay.turn][replay.piece_at(square).piece_type] += 1
        replay.push(move)
    if not any(lost.values()):
        return "nothing is captured"

    def listed(counter):
        names = [f"a {chess.piece_name(t).capitalize()}" for t in sorted(counter, reverse=True)
                 for _ in range(counter[t])]
        return ", ".join(names) or "nothing"

    parts = [f"{_side(c)} loses {listed(lost[c])}" for c in (chess.WHITE, chess.BLACK)]
    white_net, black_net = lost[chess.WHITE] - lost[chess.BLACK], lost[chess.BLACK] - lost[chess.WHITE]
    if not white_net and not black_net:
        parts.append("net, the trades are even")
    else:
        net = [f"{_side(c)} gives up {listed(n)}" for c, n in ((chess.WHITE, white_net), (chess.BLACK, black_net)) if n]
        parts.append("net, " + " and ".join(net))
    return "; ".join(parts)


def _line(board: chess.Board, pv: Sequence[str]) -> List[chess.Move]:
    """The engine line from `board`: LINE_PLIES moves, or longer while a
    tactic is still settling."""
    count = max(len(tactic_line(board, pv)), min(LINE_PLIES, len(pv)))
    replay, moves = board.copy(), []
    for uci in pv[:count]:
        move = chess.Move.from_uci(uci)
        if move not in replay.legal_moves:
            raise ValueError(f"engine line {' '.join(pv)} has illegal {uci} in {replay.fen()}")
        replay.push(move)
        moves.append(move)
    return moves


def _sans(board: chess.Board, moves: Sequence[chess.Move]) -> Tuple[str, ...]:
    replay, sans = board.copy(), []
    for move in moves:
        sans.append(replay.san(move))
        replay.push(move)
    return tuple(sans)


def _line_block(label: str, board: chess.Board, moves: Sequence[chess.Move], start: str = "",
                attack: int = 0) -> str:
    """`attack` is the index of the line's first move by the side making the
    tactic: after it, where each piece it attacks can go is stated."""
    sans = list(_sans(board, moves))
    rendered = [
        f"{label}{start}: {board.variation_san(moves)}",
        f"    FACTS: {line_facts.describe(board, sans).summary()}",
        f"    PIECES CAPTURED: {net_material(board, moves)}",
    ]
    replay, tactics = board.copy(), []
    for move in moves:
        found = events(replay, move)
        if found:
            tactics.append(f"      {replay.variation_san([move])}: {'; '.join(found)}")
        replay.push(move)
    rendered.append("    TACTICAL EVENTS (worked out from the board):" if tactics
                    else "    TACTICAL EVENTS: none (no checks by another piece, new pins or double attacks)")
    rendered += tactics
    rendered.append(walkthrough.describe(board, sans))
    if attack < len(moves):
        replay = board.copy()
        for move in moves[:attack + 1]:
            replay.push(move)
        facts = escapes(replay, moves[attack].to_square) + overloaded(replay, replay.turn)
        if facts:
            rendered.append(f"    AFTER {board.copy().variation_san(moves[:attack + 1]).split()[-1]}, "
                            "WHERE EACH PIECE IT ATTACKS CAN GO, AND ANY OVERLOADED DEFENDERS (worked out from the board):")
            rendered += [f"      - {fact}" for fact in facts]
    return "\n".join(rendered)


def brief(card: Card, rg: ReviewedGame, record: MoveRecord) -> Brief:
    board = chess.Board(record.fen)
    me, ply = rg.game.color, record.ply
    played = board.parse_san(record.san)
    after_board = board.copy()
    after_board.push(played)
    # The line with the tactic stops where the card's does, so commentary
    # can't narrate trades the card cut (a hung rook read as a combination).
    played_line = [played] + (cards.card_line(board, after_board, rg.evals[ply + 1], not me)
                              if record.kind == ALLOWED_TACTIC else _line(after_board, rg.evals[ply + 1].pv))
    best_line = (cards.card_line(board, board, rg.evals[ply], me)
                 if record.kind == MISSED_TACTIC else _line(board, rg.evals[ply].pv))

    blocks, lines, threat_fen = [], [], None
    if record.kind == MISSED_THREAT:
        passed = board.copy()
        passed.push(chess.Move.null())
        threat_fen = passed.fen()
        threat_line = cards.card_line(board, passed, rg.threats[ply], not me)
        blocks.append(_line_block(
            "LINE A - THE THREAT", passed, threat_line,
            f", what {_side(not me)} could play if it were their move now (from the card's position "
            f"with {_side(not me)} to move, FEN {threat_fen})"))
        lines.append(_sans(passed, threat_line))
    named = {MISSED_TACTIC: ("THE WINNING MOVE", "THE MOVE PLAYED, then their best reply")}.get(
        record.kind, ("THE MOVE PLAYED, then their best reply", "THE BETTER MOVE"))
    # The played line's tactic starts with their reply, its second move.
    ordered = [(named[0], best_line, 0), (named[1], played_line, 1)] if record.kind == MISSED_TACTIC \
        else [(named[0], played_line, 1), (named[1], best_line, 0)]
    for letter, (label, line, attack) in zip("BC" if threat_fen else "AB", ordered):
        blocks.append(_line_block(f"LINE {letter} - {label}", board, line, attack=attack))
        lines.append(_sans(board, line))

    best = best_line[0]
    after_best = board.copy()
    after_best.push(best)
    doing = [relations.piece(after_best, best.to_square)]
    if record.kind == MISSED_THREAT:
        avoided = (passed, threat_line[0])
    elif record.kind == ALLOWED_TACTIC:
        avoided = (after_board, played_line[1]) if len(played_line) > 1 else None
    else:
        avoided = None
    if avoided is not None:
        start, move = avoided
        label = start.variation_san([move])
        if move not in after_best.legal_moves:
            doing.append(f"after it, {label} is no longer a legal move")
        elif len(best_line) > 1:
            doing.append(f"after it, {label} is still a legal move, but the engine answers "
                         f"{after_best.variation_san([best_line[1]])} instead")
    heading = "WHAT THE WINNING MOVE DOES" if record.kind == MISSED_TACTIC else "WHAT THE BETTER MOVE DOES"

    text = "\n\n".join([
        "THE CARD\n"
        f"The player is {_side(me)}. Front: \"{card.question}\"\n"
        "Back (already shown to the player; verified):\n" + "\n".join(f"- {line}" for line in card.answer),
        f"THE POSITION ON THE CARD ({_side(me)} to move), FEN {board.fen()}\n{prompts.piece_listing(board)}",
        relations.describe(board),
        threats.describe(board),
        structure.describe(board),
        "OVERLOADED DEFENDERS (worked out from the board): "
        + ("; ".join(overloaded(board, chess.WHITE) + overloaded(board, chess.BLACK)) or "none"),
        f"{heading} ({board.variation_san([best])}), worked out from the board:\n"
        + "\n".join(f"- {fact}" for fact in doing),
        f"WHAT THE MOVE PLAYED CHANGED ({board.variation_san([played])}), worked out from the board:\n"
        + "\n".join(f"- {fact}" for fact in move_changes(board, played)),
        "ENGINE LINES (the only move sequences you may quote; each is the engine's line):\n\n"
        + "\n\n".join(blocks),
    ])
    return Brief(text=text, kind=record.kind, fen=board.fen(), threat_fen=threat_fen, lines=tuple(lines))


WHY = {
    MISSED_THREAT: "what the threat exploits (a piece undefended, overloaded, pinned, forked or trapped, "
                   "a weak square or king) and how the better move meets it",
    ALLOWED_TACTIC: "what the move played changed that the reply exploits (see WHAT THE MOVE PLAYED "
                    "CHANGED) and what the better move does instead",
    MISSED_TACTIC: "what the winning move exploits, and why the opponent can't avoid losing material",
}


def prompt(b: Brief) -> str:
    return f"""You are a chess coach writing the back of a flashcard for a club player. The card
comes from a mistake in their own game. Write to them as "you".

{b.text}

Write the commentary: two or three sentences, 70 words at most, explaining WHY
the card's answer is right, in chess terms a player can reuse: {WHY[b.kind]}.
Where TACTICAL EVENTS name the idea - a discovered or double check, a pin, a
double attack - name it. Then a last line beginning "Lesson:" with one short
habit that would have caught this during the game.

Rules:
- Every statement about a position must come from the facts above. Do not
  work out attacks, defences, pins or material yourself.
- Quote moves only as they appear in the ENGINE LINES, and sequences only as
  unbroken parts of them, with their move numbers.
- Don't repeat the card's answer (its line, material count or winning
  chances): the player has just read it. Add the reason.
- Name the deciding reason: the defender that is missing, overloaded,
  pinned or lured away; for the better move, what it changes that stops
  the tactic (WHAT THE BETTER MOVE DOES), not just that it "defends".
- Never say the opponent can't do something, or that a move is forced or
  leaves nothing to take, unless a fact above says so.
- If the facts don't show why, say less rather than guess.
- No headings, lists, bold or preamble.
"""


def board_prompt(b: Brief, pieces: List[str]) -> str:
    """review.board_prompt, for a card: a threat line starts from the card's
    position with the other side to move, which a single FEN can't say."""
    numbered = "\n".join(f"[{n}] {piece.strip()}" for n, piece in enumerate(pieces, 1))
    threat = (f"\nLINE A, the threat, starts instead from FEN {b.threat_fen}: the same position with the "
              "other side to move.") if b.threat_fen else ""
    return f"""You are checking the commentary on a chess flashcard for false statements before a student reads it.

THE BRIEF the commentary was written from:
<<<
{b.text}
>>>

THE COMMENTARY, sentence by sentence:
<<<
{numbered}
>>>

You have a board tool. The card's position is FEN {b.fen}{threat}
A position inside a line is the line's starting FEN with its moves, in SAN and
without move numbers, played up to the point the sentence is about. To ask
whether something depends on a piece, call the tool with that square in
"without".

You must use the board tool: first on the card's position, then for every
sentence that says something about a position - where a piece stands, what a
piece or move attacks, defends, pins, traps or leaves undefended, material,
check, mate, what is captured in a line - on the position that sentence is
about. Judge engine lines and evaluations against the brief.

Correct or delete every sentence the board or the brief contradicts; leave
everything else alone. The "Lesson:" line is advice: delete it only if it
rests on something false.

Your final reply must be a JSON object only, mapping the number of each
sentence to change to its full corrected text exactly as it should appear, or
to "" to delete it. Reply {{}} if nothing needs changing.
"""


_YOUR_PIECE = re.compile(r"\b[Yy]our (king|queen|rook|bishop|knight|pawn) on ([a-h][1-8])\b", re.IGNORECASE)


def _positions(b: Brief) -> List[chess.Board]:
    """The card's position and every position inside its lines."""
    starts = [chess.Board(b.fen)]
    found = [starts[0]]
    for index, line in enumerate(b.lines):
        replay = chess.Board(b.threat_fen if b.threat_fen and index == 0 else b.fen)
        for san in line:
            replay.push_san(san)
            found.append(replay.copy(stack=False))
    return found


def wrong_owner(text: str, b: Brief) -> List[str]:
    """"Your <piece> on <square>" where the player never has that piece
    there: the opponent's piece called yours. Rounds 1 and 3 did this four
    times, and the checks didn't catch it; the board can."""
    player = chess.Board(b.fen).turn
    positions = _positions(b)
    wrong = []
    for match in _YOUR_PIECE.finditer(text):
        kind = chess.PIECE_NAMES.index(match.group(1).lower())
        square = chess.parse_square(match.group(2).lower())
        if not any((p := board.piece_at(square)) is not None and p.color == player and p.piece_type == kind
                   for board in positions):
            wrong.append(f"your {match.group(1).lower()} on {match.group(2).lower()}")
    return wrong


def write(b: Brief, generate: Callable[[str], str],
          board_check: Optional[Callable[[str], str]] = None, attempts: int = 2) -> Optional[Commentary]:
    """Draft, check against the brief, check on the board, verify the moves.
    None if no attempt survives: no commentary beats a confident invention."""
    board = chess.Board(b.fen)
    for _ in range(attempts):
        draft = generate(prompt(b)).strip()
        try:
            pieces = review.sentences(draft)
            text = review.apply(pieces, generate(review.edit_prompt(b.text, pieces)))
            if board_check is not None:
                pieces = review.sentences(text)
                text = review.apply(pieces, board_check(board_prompt(b, pieces)))
        except review.ReviewError:
            continue
        text = text.strip()
        if (text and verifier.verify(text, board, sanctioned_lines=[list(line) for line in b.lines]).ok
                and not wrong_owner(text, b)):
            return Commentary(draft=draft, text=text)
    return None
