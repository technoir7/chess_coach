import json

from src.games import app_deck
from tests.test_anki import card


class TestDeckJson:
    def test_carries_what_the_app_needs_to_play_the_card(self):
        [entry] = app_deck.deck([card()], {})["cards"]
        assert entry["line_fen"].endswith(" w KQkq - 3 4") and entry["line"] == ["h5f7"]
        assert entry["orientation"] == "black"
        assert entry["arrows"] == [{"move": "h5f7", "role": "threat"}, {"move": "g7g6", "role": "best"}]
        assert entry["commentary"] is None

    def test_commentary_by_card_id(self):
        [entry] = app_deck.deck([card()], {"g-5": "The queen and bishop hit f7."})["cards"]
        assert entry["commentary"] == "The queen and bishop hit f7."

    def test_newest_games_first(self):
        old, new = card(id="a-1", played_on="2019-03-02"), card(id="b-1", played_on="2025-01-09")
        assert [c["id"] for c in app_deck.deck([old, new], {})["cards"]] == ["b-1", "a-1"]

    def test_written_as_json(self, tmp_path):
        path = tmp_path / "deck.json"
        app_deck.write(app_deck.deck([card()], {}), path)
        assert json.loads(path.read_text())["cards"][0]["id"] == "g-5"
