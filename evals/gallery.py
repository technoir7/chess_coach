"""The public gallery (docs/index.html): every answer of the first and last
rounds, as the player saw it, with the false claims its blind reviewers found.

    env/bin/python -m evals.gallery      # writes docs/gallery.json and docs/pieces/

Nothing is chosen: a round's every position is shown, the wrong ones included.
"""

import json
from pathlib import Path
from typing import Dict, List

import chess
import chess.svg

from evals.score import _read, round_dir

DOCS = Path(__file__).resolve().parent.parent / "docs"

# The answers the README's table reports for each round shown.
ROUNDS = {1: "claude-sonnet", 12: "claude-sonnet-edit-board"}


def round_rows(number: int) -> List[Dict]:
    """One row per position: the board, the engine's first choice, the text the
    player saw (None when the checker fell back to an engine-only summary) and
    the false claims labelled in it."""
    folder = round_dir(number)
    model = ROUNDS[number]
    positions = {p["id"]: p for p in _read(folder / "positions.jsonl")}
    claims = {
        (entry["id"], entry["attempt"]): entry["claims"]
        for entry in _read(folder / "labels.jsonl")
        if entry["model"] == model
    }
    responses = [
        r
        for path in sorted(folder.glob(f"responses-{model}*.jsonl"))
        for r in _read(path)
        if r["model"] == model
    ]
    rows = []
    for response in sorted(responses, key=lambda r: r["id"]):
        position = positions[response["id"]]
        board = chess.Board(position["fen"])
        fallback = response["outcome"] == "fallback"
        last = len(response["attempts"]) - 1
        rows.append({
            "id": response["id"],
            "fen": position["fen"],
            "to_move": "White" if board.turn == chess.WHITE else "Black",
            "move_number": board.fullmove_number,
            "eval_cp": position["eval_cp"],
            "best": position["lines"][0][0],
            # the squares of the engine's first choice, to mark on the board
            "best_squares": _squares(board, position["lines"][0][0]),
            "line": position["lines"][0],
            "fallback": fallback,
            "text": None if fallback else response["attempts"][last]["text"],
            "claims": [] if fallback else [
                {"quote": c["quote"], "why": c["why"]} for c in claims[(response["id"], last)]
            ],
        })
    return rows


def _squares(board: chess.Board, san: str) -> List[str]:
    move = board.parse_san(san)
    return [chess.square_name(move.from_square), chess.square_name(move.to_square)]


def main() -> None:
    gallery = {str(n): round_rows(n) for n in ROUNDS}
    (DOCS / "gallery.json").write_text(json.dumps(gallery, separators=(",", ":")) + "\n")
    pieces = DOCS / "pieces"
    pieces.mkdir(exist_ok=True)
    for symbol in "PNBRQKpnbrqk":
        name = ("w" if symbol.isupper() else "b") + symbol.upper()
        (pieces / f"{name}.svg").write_text(chess.svg.piece(chess.Piece.from_symbol(symbol)))
    for n, rows in gallery.items():
        print(f"round {n}: {len(rows)} answers, {sum(1 for r in rows if r['claims'])} with a false claim")


if __name__ == "__main__":
    main()
