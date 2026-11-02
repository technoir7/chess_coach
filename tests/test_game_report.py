from datetime import datetime, timezone

import chess
import pytest

from src.games import report
from src.games.game import Game
from src.games.move_review import ALLOWED_TACTIC, MISSED_THREAT, QUIET, MoveRecord, ReviewedGame
from src.games.win_chances import Eval


def game(id="g", speed="blitz", result="loss", termination="resign", year=2026,
         opening="French Defense: Knight Variation", color=chess.WHITE, plies=40):
    return Game(
        id=id, played_at=datetime(year, 1, 1, tzinfo=timezone.utc), speed=speed, rated=True,
        color=color, result=result, termination=termination, moves=("e4",) * plies, clocks=None,
        initial=300, increment=0, opening=opening, my_rating=1500, opponent_rating=1500,
        url=f"https://lichess.org/{id}",
    )


def move(ply=0, kind=None, drop=0.0, phase="Middlegame", low_clock=False, spent=5.0):
    return MoveRecord(
        ply=ply, san="e4", best_san="d4", fen=chess.STARTING_FEN, phase=phase,
        before=50.0, after=50.0 - drop, seconds_left=100.0, seconds_spent=spent,
        low_clock=low_clock, kind=kind,
    )


def reviewed(g, records, evals=None):
    return ReviewedGame(g, records, evals or [Eval(cp=0)] * (len(g.moves) + 1))


class TestBySpeed:
    def test_counts_games_score_and_mistakes(self):
        games = [
            reviewed(game("a", result="win"), [move(kind=QUIET, drop=12), move(), move(kind=MISSED_THREAT, drop=40)]),
            reviewed(game("b", result="draw"), [move()]),
            reviewed(game("c", speed="rapid", termination="outoftime"), [move(kind=QUIET, drop=11)]),
        ]
        [blitz, rapid] = report.by_speed(games)
        assert blitz.speed == "blitz" and blitz.games == 2
        assert blitz.score == pytest.approx(75.0)
        assert blitz.mistakes_per_game == pytest.approx(1.0)
        assert blitz.blunders_per_game == pytest.approx(0.5)
        assert rapid.lost_on_time == pytest.approx(100.0)


class TestKinds:
    def test_counts_each_kind_and_low_clock_apart(self):
        games = [reviewed(game(), [
            move(kind=MISSED_THREAT, drop=20), move(kind=MISSED_THREAT, drop=20),
            move(kind=ALLOWED_TACTIC, drop=20), move(kind=QUIET, drop=20, low_clock=True), move(),
        ])]
        counts = report.kind_counts(games)
        assert counts == {MISSED_THREAT: 2, ALLOWED_TACTIC: 1, report.LOW_CLOCK: 1}


class TestConversion:
    def test_a_winning_position_not_won(self):
        evals = [Eval(cp=0)] * 20 + [Eval(cp=600)] + [Eval(cp=0)] * 20
        games = [
            reviewed(game("a", result="draw"), [], evals),
            reviewed(game("b", result="win"), [], evals),
            reviewed(game("c", result="loss"), []),
        ]
        conversion = report.conversion(games)
        assert conversion.reached == 2 and conversion.won == 1

    def test_winning_is_from_the_players_side(self):
        evals = [Eval(cp=0)] * 20 + [Eval(cp=600)] + [Eval(cp=0)] * 20
        games = [reviewed(game("a", color=chess.BLACK), [], evals)]
        assert report.conversion(games).reached == 0


class TestClock:
    def test_mistake_rate_with_and_without_time(self):
        games = [reviewed(game(), [
            move(low_clock=True, kind=QUIET, drop=20), move(low_clock=True),
            move(), move(), move(), move(kind=QUIET, drop=20),
        ])]
        clock = report.clock_rates(games)
        assert clock.low_moves == 2 and clock.low_mistakes == 1
        assert clock.normal_moves == 4 and clock.normal_mistakes == 1


class TestOpenings:
    def test_groups_by_family_and_reads_the_position_after_move_ten(self):
        evals = [Eval(cp=0)] * 20 + [Eval(cp=-300)] + [Eval(cp=0)] * 20
        games = [reviewed(game(str(i)), [], evals) for i in range(5)]
        [row] = report.openings(games, minimum=5)
        assert row.name == "French Defense"
        assert row.games == 5
        assert row.win_chance_after_10 == pytest.approx(24.8, abs=0.1)

    def test_skips_rare_openings(self):
        games = [reviewed(game(str(i)), []) for i in range(4)]
        assert report.openings(games, minimum=5) == []


class TestMarkdown:
    def test_renders_every_section(self):
        games = [reviewed(game("a", result="win"), [move(ply=4, kind=MISSED_THREAT, drop=40)])]
        text = report.render(games, username="example_player")
        for heading in ("By time control", "What kind of mistakes", "Clock", "Game phase",
                        "Winning positions", "Openings", "By year", "Biggest mistakes"):
            assert heading in text
        assert "https://lichess.org/a#5" in text
