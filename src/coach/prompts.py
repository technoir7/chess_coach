"""Prompt construction for the coach.

Everything here is a pure function of a board plus already-computed engine
facts. Nothing in this module talks to an engine, an LLM or the network, so the
wording the model actually receives can be asserted on directly in tests.
"""

from typing import List, Optional

import chess

from src.models import CandidateLine, CoachSpeechRules, TruthPacket
from src.coach import line_facts, positional, relations, structure, walkthrough

# Small local models infer development from coordinates badly - they claimed
# developed bishops on move 1 - so the facts below are stated rather than implied.

EVALUATION_SCALE = """EVALUATION SCALE (Centipawns):
- 0 to 40: Equal / Normal opening edge
- 41 to 100: Slight advantage
- 101 to 250: Clear/Significant advantage
- 251+: Decisive advantage / Winning"""

GROUNDING_RULES = """INSTRUCTIONS:
1. Use the scale above to describe the evaluation. Do NOT call +36cp "significant".
2. Before mentioning a piece on a square, verify it exists in the position listing above.
2b. The Stockfish evaluation is the ONLY evaluation. The human-intuition reading
   is a separate signal on a different scale - describe it as how a club player
   would feel, and do NOT say the two "agree", compare them, or quote a number for it.
3. LEGAL MOVES CHECK: You MUST NOT suggest any move for the current player that is NOT in the "LEGAL MOVES" list above.
   - If a move you want to suggest is not in that list, IT IS ILLEGAL (e.g. piece is pinned).
   - Do NOT say "Black can capture..." if the capture is not in the legal moves list.
4. CRITICAL - QUOTE LINES, NEVER CALCULATE THEM:
   - You CANNOT work out a sequence of moves yourself. You WILL hallucinate.
   - The ENGINE LINES above were searched by the engine. They are the ONLY
     sequences you may give. Quote them exactly, in the order shown.
   - You may quote part of a line, but you must NOT reorder it, extend it past
     where it ends, or join moves from two different lines together.
   - If asked "what happens after X?", quote the line that begins with X and
     explain it in words. If no line above begins with X, say that the engine
     did not search that continuation - do NOT work it out yourself.
   - Explaining WHY a quoted line makes sense is welcome. Adding moves to it is not.
5. WHAT PIECES DO: say a piece attacks, defends, protects, supports or pins
   something only if PIECE RELATIONS above says so - or, for a position inside
   an engine line, its MOVE BY MOVE or POSITION AT THE END OF THIS LINE facts.
   Lines are blocked by any piece in the way, and a bishop only ever reaches
   squares of its own colour.
6. FORCED MOVES: an engine line shows the engine's choice, not the only move.
   Say a reply is forced, or that a side must or has to play it, only if MOVE
   BY MOVE says that reply is forced.
7. COUNTING: take material, doubled, isolated and passed pawns and open files
   from MATERIAL AND PAWNS (or a line's end-position facts). Do not count them
   yourself.
8. POSITIONAL CLAIMS: say a side is better in pawn structure, piece placement,
   mobility, king safety, space or passed pawns only as POSITIONAL FACTORS
   says, and that a line improves or worsens one only as its POSITIONAL CHANGE
   says. Explain a factor by what it scores (given in brackets beside it),
   with pieces and squares taken from the facts above. Say why the engine
   ranks a quiet move first only as WHY THE ENGINE RANKS IT FIRST says: a move
   it calls about as good is about as good, so do not call either better; and
   where it says reasons these factors do not show, say plainly that the
   engine sees something they do not, and give no reason of your own - a
   made-up reason teaches the wrong lesson."""

PIECE_NAMES = {
    "P": "Pawn", "N": "Knight", "B": "Bishop",
    "R": "Rook", "Q": "Queen", "K": "King",
}


def piece_listing(board: chess.Board) -> str:
    """Every piece and the square it stands on, by colour."""
    white, black = [], []
    for square, piece in board.piece_map().items():
        name = PIECE_NAMES.get(piece.symbol().upper(), piece.symbol().upper())
        entry = f"{name} on {chess.square_name(square)}"
        (white if piece.color == chess.WHITE else black).append(entry)

    return (
        "White pieces: " + ", ".join(sorted(white)) + "\n"
        "Black pieces: " + ", ".join(sorted(black))
    )


def development_status(board: chess.Board) -> str:
    """Which non-pawn pieces are off their starting squares, and where they are.

    Naming the square a piece now occupies matters: an earlier version reported
    only the square a piece had left ("knight from g1"), and the model filled in
    the destination itself - claiming White had played Nc3 in a game where it
    had played Nf3.
    """
    start_squares = {
        (piece.piece_type, piece.color): set()
        for piece in chess.Board().piece_map().values()
    }
    for square, piece in chess.Board().piece_map().items():
        start_squares[(piece.piece_type, piece.color)].add(square)

    developed = {chess.WHITE: [], chess.BLACK: []}
    at_home = {chess.WHITE: [], chess.BLACK: []}

    for square, piece in board.piece_map().items():
        if piece.piece_type == chess.PAWN:
            continue
        name = f"{chess.piece_name(piece.piece_type).capitalize()} on {chess.square_name(square)}"
        if square not in start_squares.get((piece.piece_type, piece.color), set()):
            developed[piece.color].append(name)
        elif piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            at_home[piece.color].append(name)

    lines = []
    for color, label in ((chess.WHITE, "White"), (chess.BLACK, "Black")):
        if developed[color]:
            lines.append(f"{label} pieces off their starting squares: "
                         + ", ".join(sorted(developed[color])))
        else:
            lines.append(
                f"{label} has NOT developed any piece - all pieces are on their starting squares."
            )
        # Stated as well as implied: "Nbd2 develops the last minor piece" was
        # written with the f1 bishop still at home.
        lines.append(
            f"{label} minor pieces still on their starting squares: "
            + (", ".join(sorted(at_home[color])) or "none")
        )
    return "\n".join(lines)


def legal_moves_list(board: chess.Board) -> str:
    return ", ".join(sorted(board.san(move) for move in board.legal_moves))


# Queen and a minor piece (12), or rook, bishop and knight (11), per side.
ENDGAME_MATERIAL = 13


def game_phase(board: chess.Board) -> str:
    """Endgame by what is left on the board, not by how long the game has run:
    counting moves alone called a position with every piece still on it an
    endgame at move 22."""
    non_pawn = [
        sum(line_facts.PIECE_VALUES[t] * len(board.pieces(t, color))
            for t in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN))
        for color in (chess.WHITE, chess.BLACK)
    ]
    if max(non_pawn) <= ENDGAME_MATERIAL:
        return "Endgame"
    return "Opening" if board.ply() < 15 else "Middlegame"


def recent_moves(board: chess.Board, limit: int = 30) -> str:
    """Move history in SAN with correct numbering, most recent `limit` plies.

    Truncation is stated explicitly - the prompt tells the model this is the
    whole game, so a silently clipped history would make that a lie.
    """
    if not board.move_stack:
        return "Game just started"

    truncated = len(board.move_stack) > limit

    replay = board.copy()
    moves = [replay.pop() for _ in range(min(limit, len(board.move_stack)))]
    moves.reverse()

    lines, current = [], ""
    for move in moves:
        san = replay.san(move)
        if replay.turn == chess.WHITE:
            current = f"{replay.fullmove_number}. {san}"
        elif current:
            lines.append(f"{current} {san}")
            current = ""
        else:
            lines.append(f"{replay.fullmove_number}. ... {san}")
        replay.push(move)

    if current:
        lines.append(current)
    if truncated:
        lines.insert(0, "(earlier moves omitted)")
    return "\n".join(lines)


def format_eval(eval_cp: Optional[float]) -> str:
    """Centipawns are whole numbers; a trailing .0 is noise in the prompt."""
    return "unknown" if eval_cp is None else str(int(eval_cp))


def eval_band(eval_cp: float) -> str:
    """The EVALUATION SCALE's word for a number, stated beside it.

    With the scale twenty lines away, -670cp was called "a clear edge" - the
    scale's word for 101-250.
    """
    size = abs(eval_cp)
    if size <= 40:
        return "roughly equal"
    side = "White" if eval_cp > 0 else "Black"
    band = "slight" if size <= 100 else "clear" if size <= 250 else "decisive"
    return f"{band} advantage for {side}"


def _with_band(eval_cp: Optional[float]) -> str:
    return format_eval(eval_cp) if eval_cp is None else f"{format_eval(eval_cp)}cp, {eval_band(eval_cp)}"


def vibe_reading(vibe_score: Optional[float]) -> str:
    """Describe the Leela reading in words rather than as a number.

    Maia-1500 is a club-strength, human-like network searched at 100 nodes -
    it answers "what would a 1500 player feel here", not "how good is this
    position". Printing its raw value beside a depth-15 Stockfish evaluation
    invited the model to treat the two as comparable and report that they
    agreed, when they are not even on the same scale.
    """
    if vibe_score is None:
        return "unavailable"

    magnitude = abs(vibe_score)
    if magnitude <= 0.5:
        return "a club-strength human would read this as roughly balanced"

    side = "White" if vibe_score > 0 else "Black"
    if magnitude <= 1.5:
        return f"a club-strength human would lean towards {side}"
    return f"a club-strength human would clearly prefer {side}"


def numbered_line(line_san: List[str], board: chess.Board) -> str:
    """Render a SAN sequence with correct move numbers from this position."""
    number = board.fullmove_number
    white_to_move = board.turn == chess.WHITE

    parts = []
    for index, san in enumerate(line_san):
        if white_to_move:
            parts.append(f"{number}. {san}")
        else:
            parts.append(san if index else f"{number}... {san}")
            number += 1
        white_to_move = not white_to_move
    return " ".join(parts)


def engine_lines(packet: TruthPacket, board: chess.Board) -> str:
    """The continuations the engine actually searched, quotable verbatim."""
    if not packet.candidate_lines:
        return "ENGINE LINES: none available - do not give any move sequence."

    rendered = ["ENGINE LINES (searched by the engine - the ONLY sequences you may quote):"]
    for line in packet.candidate_lines:
        rendered.append(
            f"- after {line.move_san} ({_with_band(line.eval_cp)}): "
            f"{numbered_line(line.line_san, board)}"
        )
        # Stated rather than left to inference: the model has described a
        # checking move as an attack on a piece, and claimed queens were
        # exchanged in a line where nothing was captured.
        facts = line_facts.describe(board, line.line_san)
        rendered.append(f"    FACTS: {facts.summary()}")
        rendered.append(f"    KIND: {_kind(facts, line)}")
        rendered.append(f"    POSITIONAL CHANGE BY THE END OF THIS LINE{_positional_change(board, line, facts, packet)}")
        if line is packet.candidate_lines[0] and len(packet.candidate_lines) > 1 and _is_quiet(facts, line):
            rendered.append(f"    WHY THE ENGINE RANKS IT FIRST: {_why_first(board, packet)}")
        rendered.append(walkthrough.describe(board, line.line_san))
    return "\n".join(rendered)


# Below this, two moves are as good as each other: a depth-15 evaluation
# moves by about this much from one depth to the next. Below SMALL_GAP the
# difference stays inside the scale's "equal" band.
ABOUT_AS_GOOD = 20
SMALL_GAP = 50
# A point of material is worth about 100cp. A line a point down but less than
# half that worse leaves compensation the engine sees, so the lost point is
# not why it is worse (round 8, p092: a point down and 24cp worse).
COMPENSATED = 50


def _why_first(board: chess.Board, packet: TruthPacket) -> str:
    """Why the engine puts a quiet move above each of its other lines, from
    what is known to be true: the two are about as good, the other loses
    material, or the factors where the lines end differ. Otherwise the model
    is told to say the reason is not shown: an engine's search often sees
    something no static factor scores, and an invented reason teaches the
    wrong lesson."""
    first, mover = packet.candidate_lines[0], board.turn
    side = "White" if mover == chess.WHITE else "Black"
    sign = 1 if mover == chess.WHITE else -1
    parts = []
    for other in packet.candidate_lines[1:]:
        if first.eval_cp is None or other.eval_cp is None:
            parts.append(f"{other.move_san} has no evaluation to compare")
            continue
        gap = int(sign * (first.eval_cp - other.eval_cp))
        if gap < ABOUT_AS_GOOD:
            parts.append(f"{other.move_san} is about as good ({gap}cp behind, too little to matter); do not call either better")
            continue
        lost = -sign * line_facts.describe(board, other.line_san).material_won
        if lost > 0 and gap >= COMPENSATED * lost:
            parts.append(f"{other.move_san} is {gap}cp worse: its line loses {line_facts.points(lost)} of material for {side}")
            continue
        compared = positional.contrast(mover, first.factors_after, other.factors_after)
        if compared and compared[0] >= positional.SHOWN:
            detail = compared[1] or (
                f"small differences in several factors that add up to {compared[0]:.2f} for {side}"
            )
            parts.append(
                f"{other.move_san} is {gap}cp worse; compared with {other.move_san}'s line, "
                f"{first.move_san}'s ends with {detail}"
            )
            continue
        worse = f"is slightly worse ({gap}cp, a small difference)" if gap < SMALL_GAP else f"is {gap}cp worse"
        parts.append(
            f"{other.move_san} {worse}, for reasons these factors do not show; say the engine "
            f"sees something they do not, and {_NO_REASON}"
        )
    return "; ".join(parts)


_NO_REASON = "do not give a reason of your own"


# The engine reports a mate in n as 10000 - n centipawns.
_MATE_SCORES = 9000


def _is_mate_score(eval_cp: Optional[float]) -> bool:
    return eval_cp is not None and abs(eval_cp) >= _MATE_SCORES


def _is_quiet(facts: line_facts.LineFacts, line: CandidateLine) -> bool:
    return _is_positional(facts) and not _is_mate_score(line.eval_cp)


def _is_positional(facts: line_facts.LineFacts) -> bool:
    return not facts.material_won and not any(move.is_mate for move in facts.moves)


def _kind(facts: line_facts.LineFacts, line: CandidateLine) -> str:
    if _is_mate_score(line.eval_cp) and not any(move.is_mate for move in facts.moves):
        return "tactical (the engine sees a forced mate beyond the moves shown)"
    if _is_positional(facts):
        return "positional (no material is won; what the line gains is in the position)"
    if any(move.is_mate for move in facts.moves):
        return "tactical (it ends in mate)"
    side = "White" if facts.material_won > 0 else "Black"
    return f"tactical ({side} wins {line_facts.points(abs(facts.material_won))} of material)"


def _positional_change(
    board: chess.Board, line: CandidateLine, facts: line_facts.LineFacts, packet: TruthPacket,
) -> str:
    change = positional.change(
        line_facts.settled(board, line.line_san), packet.factors, line.factors_after
    )
    if facts.exchange:
        return f" (with the exchange on {facts.cut_mid_exchange} played out: {' '.join(facts.exchange)}): {change}"
    return f": {change}"


def position_facts(board: chess.Board, packet: TruthPacket, opening_info: str) -> str:
    """The verified-facts block shared by every coach prompt.

    Renders the Truth Packet and the board it describes - nothing else reaches
    the model, which is what keeps the narration bound to verified facts.
    """
    side = "White" if board.turn == chess.WHITE else "Black"
    return f"""GAME STATE: Move {board.fullmove_number}, {side} to move - {packet.game_phase} phase

CURRENT POSITION:
{piece_listing(board)}

{relations.describe(board)}

{structure.describe(board)}

{positional.describe(board, packet.factors)}

DEVELOPMENT:
{development_status(board)}

{opening_info}

LEGAL MOVES (STRICTLY ENFORCED):
{legal_moves_list(board)}

Stockfish Evaluation: {format_eval(packet.engine_eval)} centipawns{"" if packet.engine_eval is None else f" ({eval_band(packet.engine_eval)})"}
Human intuition (Maia-1500, a club-strength human-like net - NOT a second
evaluation, and not on the same scale as the number above):
{vibe_reading(packet.vibe_score)}
Top Moves: {', '.join(packet.top_moves_san) if packet.top_moves_san else 'N/A'}

{engine_lines(packet, board)}

{EVALUATION_SCALE}"""


def explain_prompt(facts: str, history: str) -> str:
    """Explanation of the current position.

    The move history is included because without it the model invents one -
    it described a move White had never played when given only the position.
    """
    return f"""You are a chess coach analyzing this position.

{facts}

MOVES PLAYED SO FAR (no other move has been played, apart from any marked as omitted):
{history}

{GROUNDING_RULES}

Explain the current position in two short parts, each starting on its own line:
Tactics: what is forcing right now - threats, pins, and the lines marked
KIND: tactical (what they win and how). A line marked KIND: positional does not
belong here, even if it has captures or checks in it. If nothing is forcing,
say so in one sentence.
Position: the long-term picture - where a side is ahead in POSITIONAL FACTORS,
and the lines marked KIND: positional: what each changes (its POSITIONAL
CHANGE) and why that matters. Take most care here: for a quiet first choice,
say why it is ranked first as its WHY THE ENGINE RANKS IT FIRST gives it -
including that other moves are about as good, where it says so.
Each engine line goes in the part its KIND names. Keep the two apart, and
mention one in the other only where they meet - a tactic that also changes the
position, or a positional factor a tactic rests on.
A few sentences per part. Be accurate, and talk about the current position only.
"""


def chat_prompt(facts: str, history: str, question: str) -> str:
    return f"""You are an interactive chess coach. The user is asking about the current position.

{facts}

MOVES PLAYED SO FAR (no other move has been played, apart from any marked as omitted):
{history}

User's Question: {question}

{GROUNDING_RULES}

Provide a helpful, accurate response about the current position only.
"""


def advice_prompt(facts: str, rules: CoachSpeechRules) -> str:
    """In-game advice, fired when the logic gate detects a real event.

    Carries the same grounding rules as every other path - this one goes out
    mid-game, where an invented move would be most damaging.
    """
    return f"""You are a chess coach. Something in this position just changed for the worse.

{facts}

COACH RULES:
You must: {', '.join(rules.must)}
You must not: {', '.join(rules.must_not)}

{GROUNDING_RULES}

Give one short, punchy piece of advice for the player. Do not name a move unless
it appears in the engine's top moves above.
"""


def theme_prompt(fen: str, eval_cp: Optional[float]) -> str:
    return f"""Chess coach: 3 word positional theme for FEN: {fen} (Eval: {format_eval(eval_cp)})
Example: "Closed tactical middlegame"
Respond ONLY with the theme.
"""
