"""Cards as the JSON deck the phone app (cards_app/) plays.

The app has the player make the line's first move on a board, so a card
goes out with its moves as UCI rather than only as text. Newest games come
first: recent habits are the ones worth fixing.
"""

import json
from pathlib import Path
from typing import Dict, Sequence

import chess

from src.games.cards import Card


def deck(cards: Sequence[Card], notes: Dict[str, str]) -> dict:
    ordered = sorted(cards, key=lambda c: (c.played_on, c.id), reverse=True)
    return {"cards": [_entry(card, notes.get(card.id)) for card in ordered]}


def _entry(card: Card, note) -> dict:
    return {
        "id": card.id,
        "kind": card.kind,
        "fen": card.fen,
        "orientation": "white" if card.orientation == chess.WHITE else "black",
        "question": card.question,
        "shown_move": card.shown_move,
        "answer": list(card.answer),
        "arrows": [{"move": move, "role": role} for move, role in card.arrows],
        "line_fen": card.line_fen,
        "line": list(card.line),
        "tags": list(card.tags),
        "played_on": card.played_on,
        "link": card.link,
        "commentary": note,
    }


def write(data: dict, path: Path) -> None:
    path.write_text(json.dumps(data, indent=1))
