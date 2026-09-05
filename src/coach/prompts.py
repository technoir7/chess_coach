"""Prompt construction for the coach.

Everything here is a pure function of a board plus already-computed engine
facts. Nothing in this module talks to an engine, an LLM or the network, so the
wording the model actually receives can be asserted on directly in tests.
"""

from typing import List, Optional

import chess

from src.models import CoachSpeechRules, TruthPacket

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
   - Explaining WHY a quoted line makes sense is welcome. Adding moves to it is not."""

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

    for square, piece in board.piece_map().items():
        if piece.piece_type == chess.PAWN:
            continue
        if square not in start_squares.get((piece.piece_type, piece.color), set()):
            developed[piece.color].append(
                f"{chess.piece_name(piece.piece_type).capitalize()} on "
                f"{chess.square_name(square)}"
            )

    lines = []
    for color, label in ((chess.WHITE, "White"), (chess.BLACK, "Black")):
        if developed[color]:
            lines.append(f"{label} pieces off their starting squares: "
                         + ", ".join(sorted(developed[color])))
        else:
            lines.append(
                f"{label} has NOT developed any piece - all pieces are on their starting squares."
            )
    return "\n".join(lines)


def legal_moves_list(board: chess.Board) -> str:
    return ", ".join(sorted(board.san(move) for move in board.legal_moves))


def game_phase(board: chess.Board) -> str:
    move_count = len(board.move_stack)
    if move_count < 15:
        return "Opening"
    return "Middlegame" if move_count < 40 else "Endgame"


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
            f"- after {line.move_san} ({format_eval(line.eval_cp)}cp): "
            f"{numbered_line(line.line_san, board)}"
        )
    return "\n".join(rendered)


def position_facts(board: chess.Board, packet: TruthPacket, opening_info: str) -> str:
    """The verified-facts block shared by every coach prompt.

    Renders the Truth Packet and the board it describes - nothing else reaches
    the model, which is what keeps the narration bound to verified facts.
    """
    return f"""GAME STATE: Move {len(board.move_stack)} - {packet.game_phase} phase

CURRENT POSITION:
{piece_listing(board)}

DEVELOPMENT:
{development_status(board)}

{opening_info}

LEGAL MOVES (STRICTLY ENFORCED):
{legal_moves_list(board)}

Stockfish Evaluation: {format_eval(packet.engine_eval)} centipawns
Leela Vibe Score: {packet.vibe_score if packet.vibe_score is not None else 'N/A'}
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

MOVES PLAYED SO FAR (this is the complete game - no other move has been played):
{history}

{GROUNDING_RULES}

Provide a concise, accurate explanation of the current position only.
"""


def chat_prompt(facts: str, history: str, question: str) -> str:
    return f"""You are an interactive chess coach. The user is asking about the current position.

{facts}

MOVES PLAYED SO FAR (this is the complete game - no other move has been played):
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
