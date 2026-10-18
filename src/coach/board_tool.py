"""A board the model can ask about while it checks its own draft.

Round 6's remaining false answers were caught by reviewers who checked each
claim on a board with python-chess, and missed by the model checking against
facts computed in advance: every error left needed a fact nobody thought to
precompute ("without the d7 rook, is it still mate?"). So the check gets the
same thing the reviewers had - a board to ask - as a single tool.

The tool is served over MCP on stdin/stdout, with no shell and no files: the
model can describe positions and nothing else.

    python -m src.coach.board_tool     # the server `claude --mcp-config` starts
"""

import json
import sys
from typing import Dict, List, Optional, Sequence

import chess

from src.coach import prompts, relations, structure

PROTOCOL_VERSION = "2024-11-05"

TOOL = {
    "name": "board",
    "description": (
        "Describe a chess position: where every piece stands, what each attacks "
        "and defends, pins, material and pawn structure, development, and the "
        "legal moves of both sides. Give a FEN and, optionally, moves in SAN to "
        "play from it first, and squares to empty first (to ask 'what if this "
        "piece were not there')."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "fen": {"type": "string", "description": "the starting position"},
            "moves": {"type": "array", "items": {"type": "string"}, "description": "SAN moves to play first"},
            "without": {"type": "array", "items": {"type": "string"}, "description": "squares to empty first"},
        },
        "required": ["fen"],
    },
}


def _side(color: chess.Color) -> str:
    return "White" if color == chess.WHITE else "Black"


def _legal(board: chess.Board) -> str:
    return ", ".join(sorted(board.san(m) for m in board.legal_moves)) or "none"


def report(fen: str, moves: Sequence[str], without: Sequence[str] = ()) -> str:
    """Everything the coach's facts say about one position, for the model to read."""
    try:
        board = chess.Board(fen)
    except ValueError:
        return f"{fen!r} is not a valid FEN."
    for name in without:
        try:
            board.remove_piece_at(chess.parse_square(name.strip().lower()))
        except ValueError:
            return f"{name!r} is not a square."
    for san in moves:
        try:
            board.push_san(san)
        except ValueError:
            return f"{san} is not legal in the position reached before it ({board.fen()})."

    side = _side(board.turn)
    state = "checkmate" if board.is_checkmate() else "stalemate" if board.is_stalemate() else (
        f"{side} is in check" if board.is_check() else "no check")
    other = board.copy(stack=False)
    other.turn = not board.turn
    other_side = _side(other.turn)
    return "\n".join([
        f"FEN: {board.fen()}",
        f"{side} to move; {state}.",
        prompts.piece_listing(board),
        relations.describe(board),
        structure.describe(board),
        prompts.development_status(board),
        f"Legal moves for {side} (to move): {_legal(board)}",
        f"Legal moves {other_side} would have if it were {other_side}'s turn: {_legal(other)}",
    ])


def _result(id_, result: Dict) -> Dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def handle(message: Dict) -> Optional[Dict]:
    """The reply to one JSON-RPC message, or None for a notification."""
    method, id_ = message.get("method"), message.get("id")
    if id_ is None:
        return None
    if method == "initialize":
        return _result(id_, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "board", "version": "1"},
        })
    if method == "tools/list":
        return _result(id_, {"tools": [TOOL]})
    if method == "tools/call":
        params = message.get("params") or {}
        if params.get("name") != "board":
            return {"jsonrpc": "2.0", "id": id_, "error": {"code": -32602, "message": "unknown tool"}}
        args = params.get("arguments") or {}
        text = report(str(args.get("fen", "")), list(args.get("moves") or []), list(args.get("without") or []))
        return _result(id_, {"content": [{"type": "text", "text": text}], "isError": False})
    if method == "ping":
        return _result(id_, {})
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": -32601, "message": f"no method {method}"}}


def serve(stdin=sys.stdin, stdout=sys.stdout) -> None:
    for line in stdin:
        if not line.strip():
            continue
        reply = handle(json.loads(line))
        if reply is not None:
            stdout.write(json.dumps(reply) + "\n")
            stdout.flush()


if __name__ == "__main__":
    serve()
