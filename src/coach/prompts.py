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
4. CRITICAL - NO CALCULATING VARIATIONS:
   - You CANNOT calculate multi-move sequences yourself. You will hallucinate.
   - Do NOT write lines like "1. Bxb5 Qxb5 2. Bxd7+ Kxd7 3. Qxc7+" - you WILL get this wrong.
   - ONLY mention the engine's "Top Moves" above. Do NOT invent follow-up moves.
   - If asked "what happens after X?", say "I recommend checking the engine analysis for that line."
   - Focus on describing the CURRENT position, themes, and piece activity."""

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
    """Which non-pawn pieces have left their starting squares."""
    start = chess.Board()
    moved = {chess.WHITE: [], chess.BLACK: []}

    for square, original in start.piece_map().items():
        if original.piece_type == chess.PAWN:
            continue
        if board.piece_at(square) != original:
            moved[original.color].append(
                f"{chess.piece_name(original.piece_type)} from {chess.square_name(square)}"
            )

    lines = []
    for color, label in ((chess.WHITE, "White"), (chess.BLACK, "Black")):
        if moved[color]:
            lines.append(f"{label} has moved: " + ", ".join(sorted(moved[color])))
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


def recent_moves(board: chess.Board, limit: int = 10) -> str:
    """Move history in SAN with correct numbering, most recent `limit` plies."""
    if not board.move_stack:
        return "Game just started"

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
    return "\n".join(lines)


def format_eval(eval_cp: Optional[float]) -> str:
    """Centipawns are whole numbers; a trailing .0 is noise in the prompt."""
    return "unknown" if eval_cp is None else str(int(eval_cp))


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

{EVALUATION_SCALE}"""


def explain_prompt(facts: str) -> str:
    return f"""You are a chess coach analyzing this position.

{facts}

{GROUNDING_RULES}

Provide a concise, accurate explanation of the current position only.
"""


def chat_prompt(facts: str, history: str, question: str) -> str:
    return f"""You are an interactive chess coach. The user is asking about the current position.

{facts}

RECENT MOVES:
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
