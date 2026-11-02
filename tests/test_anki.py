import json
import sqlite3
import zipfile

import chess

from src.games import anki
from src.games.cards import BEST, THREAT, Card


def card(id="g-5", question="Black to move. What is your opponent threatening?", played_on="2026-05-01"):
    return Card(
        id=id, kind="missed_threat",
        fen="r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3",
        orientation=chess.BLACK, question=question, shown_move=None,
        answer=("The threat: 4. Qxf7#, leading to mate.", "Better: 3...g6."),
        arrows=(("h5f7", THREAT), ("g7g6", BEST)),
        line_fen="r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 3 4", line=("h5f7",),
        tags=("missed_threat", "blitz"), played_on=played_on,
        link="https://lichess.org/g#6",
    )


def read_deck(path):
    unpacked = path.with_suffix("")
    with zipfile.ZipFile(path) as z:
        media = json.loads(z.read("media"))
        z.extract("collection.anki2", unpacked)
    db = sqlite3.connect(unpacked / "collection.anki2")
    notes = db.execute("select guid, flds, tags from notes").fetchall()
    return notes, media


class TestDeck:
    def test_one_note_per_card_with_board_images(self, tmp_path):
        out = tmp_path / "deck.apkg"
        anki.write_deck([card(), card(id="h-7", question="White to move. Find the best move.")], {}, out)
        notes, media = read_deck(out)
        assert len(notes) == 2
        assert all(name.endswith(".svg") for name in media.values())
        fields = notes[0][1].split("\x1f")
        assert "<img src=" in fields[0] and "threatening" in fields[1]
        assert "missed_threat" in notes[0][2]

    def test_the_same_card_keeps_its_note_id(self, tmp_path):
        anki.write_deck([card()], {}, tmp_path / "a.apkg")
        anki.write_deck([card()], {}, tmp_path / "b.apkg")
        first, _ = read_deck(tmp_path / "a.apkg")
        second, _ = read_deck(tmp_path / "b.apkg")
        assert first[0][0] == second[0][0]

    def test_text_is_escaped(self, tmp_path):
        out = tmp_path / "deck.apkg"
        anki.write_deck([card(question="White to move. Is 3 < 4?")], {}, out)
        notes, _ = read_deck(out)
        assert "Is 3 &lt; 4?" in notes[0][1]

    def test_commentary_goes_on_the_back_with_the_lesson_set_apart(self, tmp_path):
        out = tmp_path / "deck.apkg"
        text = "The queen and bishop both hit the f7 pawn & only the king guards it.\n\nLesson: Count attackers on f7."
        anki.write_deck([card()], {"g-5": text}, out)
        notes, _ = read_deck(out)
        coach = notes[0][1].split("\x1f")[4]
        assert coach == ("The queen and bishop both hit the f7 pawn &amp; only the king guards it."
                         "<br><br><b>Lesson:</b> Count attackers on f7.")
