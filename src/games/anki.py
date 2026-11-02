"""Cards as an Anki deck (.apkg), with the boards drawn as images.

genanki writes the package: the boards are 30KB SVGs each, too big to inline
into a text import, and an .apkg carries them as media alongside a note
type laid out for chess. Notes keep their id across runs, so importing a
new deck updates old cards instead of duplicating them.
"""

import hashlib
import html
import tempfile
from pathlib import Path
from typing import Dict, Sequence

import chess
import chess.svg
import genanki

from src.games.cards import BEST, PLAYED, THREAT, Card

# Fixed once: Anki matches decks and note types by these ids.
MODEL_ID = 1729406211
DECK_ID = 1729406212
DECK_NAME = "Chess::My mistakes"

ARROW_COLORS = {THREAT: "#cc0000cc", BEST: "#15781bcc", PLAYED: "#1f5fbfcc"}

CSS = """
.card { font-family: -apple-system, Helvetica, Arial, sans-serif; font-size: 18px;
        text-align: center; color: #222; background: #fafafa; }
.board img { width: 100%; max-width: 420px; }
.q { margin: 12px auto; font-weight: 600; max-width: 520px; }
.a, .coach { text-align: left; max-width: 520px; margin: 10px auto; line-height: 1.45; }
.coach { font-size: 16px; color: #444; border-top: 1px solid #ddd; padding-top: 10px; }
.link { font-size: 14px; margin-top: 14px; }
.nightMode .card { color: #eee; background: #222; }
.nightMode .coach { color: #ccc; }
"""

MODEL = genanki.Model(
    MODEL_ID,
    "Chess mistake",
    fields=[{"name": n} for n in ("Board", "Question", "AnswerBoard", "Answer", "Coach", "Link")],
    templates=[{
        "name": "Card",
        "qfmt": '<div class="board">{{Board}}</div><div class="q">{{Question}}</div>',
        "afmt": ('<div class="board">{{AnswerBoard}}</div><div class="q">{{Question}}</div>'
                 '<hr id="answer"><div class="a">{{Answer}}</div>'
                 '{{#Coach}}<div class="coach">{{Coach}}</div>{{/Coach}}'
                 '<div class="link"><a href="{{Link}}">Open the game on Lichess</a></div>'),
    }],
    css=CSS,
)


def write_deck(cards: Sequence[Card], notes: Dict[str, str], path: Path) -> None:
    """`notes` holds commentary by card id; a card without any is fine."""
    deck = genanki.Deck(DECK_ID, DECK_NAME)
    with tempfile.TemporaryDirectory() as media_dir:
        media = {}
        for card in cards:
            front = _board(card, [(card.shown_move, PLAYED)] if card.shown_move else [], media, media_dir)
            back = _board(card, card.arrows, media, media_dir)
            deck.add_note(genanki.Note(
                model=MODEL,
                fields=[
                    front,
                    html.escape(card.question),
                    back,
                    "<br>".join(html.escape(line) for line in card.answer),
                    _commentary(notes.get(card.id, "")),
                    card.link,
                ],
                tags=list(card.tags),
                guid=genanki.guid_for(card.id),
            ))
        package = genanki.Package(deck)
        package.media_files = list(media.values())
        package.write_to_file(str(path))


def _board(card: Card, arrows, media: Dict[str, str], media_dir: str) -> str:
    svg = chess.svg.board(
        chess.Board(card.fen),
        orientation=card.orientation,
        size=420,
        arrows=[chess.svg.Arrow(*_squares(uci), color=ARROW_COLORS[role]) for uci, role in arrows],
    )
    name = f"chess-{hashlib.sha1(svg.encode()).hexdigest()[:16]}.svg"
    if name not in media:
        target = Path(media_dir) / name
        target.write_text(svg)
        media[name] = str(target)
    return f'<img src="{name}">'


def _squares(uci: str):
    move = chess.Move.from_uci(uci)
    return move.from_square, move.to_square



def _commentary(text: str) -> str:
    escaped = html.escape(text.strip()).replace("\n", "<br>")
    return escaped.replace("Lesson:", "<b>Lesson:</b>", 1)
