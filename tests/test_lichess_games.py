import json

import chess
import pytest

from src.games import lichess


def raw_game(**overrides):
    game = {
        "id": "abc12345",
        "rated": True,
        "variant": "standard",
        "speed": "blitz",
        "createdAt": 1790532342317,
        "status": "resign",
        "players": {
            "white": {"user": {"name": "Someone", "id": "someone"}, "rating": 1500},
            "black": {"user": {"name": "example_player", "id": "example_player"}, "rating": 1400},
        },
        "winner": "black",
        "opening": {"eco": "C00", "name": "French Defense", "ply": 2},
        "moves": "e4 e6 d4 d5",
        "clocks": [30003, 30003, 29500, 29000],
        "clock": {"initial": 300, "increment": 0, "totalTime": 300},
    }
    game.update(overrides)
    return game


class TestParse:
    def test_reads_the_players_side_and_result(self):
        game = lichess.parse_game(raw_game(), "Example_Player")
        assert game.color == chess.BLACK
        assert game.result == "win"
        assert game.my_rating == 1400 and game.opponent_rating == 1500

    def test_no_winner_is_a_draw(self):
        game = lichess.parse_game(raw_game(winner=None, status="draw"), "example_player")
        assert game.result == "draw"

    def test_clocks_are_seconds_left_after_each_ply(self):
        game = lichess.parse_game(raw_game(), "example_player")
        assert game.clocks == (300.03, 300.03, 295.0, 290.0)

    def test_moves_and_speed(self):
        game = lichess.parse_game(raw_game(), "example_player")
        assert game.moves == ("e4", "e6", "d4", "d5")
        assert game.speed == "blitz" and game.initial == 300 and game.increment == 0

    def test_a_game_without_clocks_has_none(self):
        raw = raw_game(speed="correspondence")
        del raw["clocks"], raw["clock"]
        game = lichess.parse_game(raw, "example_player")
        assert game.clocks is None and game.initial is None

    def test_rejects_other_variants(self):
        with pytest.raises(lichess.UnsupportedGame):
            lichess.parse_game(raw_game(variant="chess960"), "example_player")

    def test_rejects_games_from_a_set_position(self):
        with pytest.raises(lichess.UnsupportedGame):
            lichess.parse_game(raw_game(variant="fromPosition"), "example_player")

    def test_rejects_a_game_the_player_is_not_in(self):
        with pytest.raises(ValueError):
            lichess.parse_game(raw_game(), "somebody_else")


class TestClockReading:
    def test_time_left_before_a_ply_is_the_movers_previous_reading(self):
        game = lichess.parse_game(raw_game(), "example_player")
        assert game.seconds_left_before(0) == 300
        assert game.seconds_left_before(2) == 300.03
        assert game.seconds_left_before(3) == 300.03

    def test_time_spent_on_a_ply(self):
        game = lichess.parse_game(raw_game(), "example_player")
        assert game.seconds_spent(3) == pytest.approx(300.03 - 290.0)

    def test_increment_is_added_back(self):
        game = lichess.parse_game(
            raw_game(clock={"initial": 300, "increment": 2, "totalTime": 380},
                     clocks=[30000, 30000, 29800, 29700]),
            "example_player",
        )
        # 300 left, +2 increment for moving, 297 left after: 5 seconds spent.
        assert game.seconds_spent(3) == pytest.approx(5)

    def test_no_clocks_means_no_reading(self):
        raw = raw_game()
        del raw["clocks"]
        game = lichess.parse_game(raw, "example_player")
        assert game.seconds_left_before(2) is None and game.seconds_spent(2) is None


class FakeResponse:
    def __init__(self, lines, status=200):
        self.lines, self.status_code = lines, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_lines(self, decode_unicode=True):
        return iter(self.lines)


class FakeSession:
    def __init__(self, response):
        self.response, self.calls = response, []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class TestDownload:
    def test_asks_for_clocks_and_names_itself(self):
        """Lichess answers 404 to a request that doesn't say what program
        is asking, so the User-Agent is part of the contract."""
        session = FakeSession(FakeResponse([json.dumps(raw_game())]))
        lichess.download_games("example_player", session=session)
        url, kwargs = session.calls[0]
        assert url.endswith("/api/games/user/example_player")
        assert kwargs["headers"]["User-Agent"]
        assert kwargs["headers"]["Accept"] == "application/x-ndjson"
        assert kwargs["params"]["clocks"] == "true"

    def test_returns_one_dict_per_line_skipping_blank_ones(self):
        session = FakeSession(FakeResponse([json.dumps(raw_game()), "", json.dumps(raw_game(id="b"))]))
        games = lichess.download_games("example_player", session=session)
        assert [g["id"] for g in games] == ["abc12345", "b"]

    def test_an_http_error_is_raised(self):
        session = FakeSession(FakeResponse([], status=404))
        with pytest.raises(RuntimeError):
            lichess.download_games("example_player", session=session)
