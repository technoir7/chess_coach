from datetime import datetime, timezone

import chess
import pytest

from src.games import move_review
from src.games.game import Game
from src.games.win_chances import Eval

LEVEL = Eval(cp=0)


def game(moves, color, clocks=None, initial=None):
    return Game(
        id="g", played_at=datetime(2026, 1, 1, tzinfo=timezone.utc), speed="blitz",
        rated=True, color=color, result="loss", termination="resign",
        moves=tuple(moves.split()), clocks=clocks, initial=initial, increment=0 if initial else None,
        opening="", my_rating=1500, opponent_rating=1500, url="https://lichess.org/g",
    )


def evals(count, **at):
    """`count` positions, level unless given: at={'p5': Eval(...)}."""
    return [at.get(f"p{i}", LEVEL) for i in range(count)]


def record(records, ply):
    return next(r for r in records if r.ply == ply)


# 1.e4 e5 2.Bc4 Nc6 3.Qh5 Nf6?? 4.Qxf7#: White threatened mate and Black ignored it.
SCHOLAR = game("e4 e5 Bc4 Nc6 Qh5 Nf6 Qxf7#", chess.BLACK)
SCHOLAR_EVALS = evals(8, p5=Eval(cp=0, pv=("g7g6",)), p6=Eval(mate=1, pv=("h5f7",)), p7=Eval(mate=1))
SCHOLAR_THREATS = {5: Eval(mate=1, pv=("h5f7",))}

# 1.e4 Nf6 2.d3 Ne4?? 3.dxe4: the knight steps onto a square the pawn covers.
DROPPED_KNIGHT = game("e4 Nf6 d3 Ne4 dxe4", chess.BLACK)

# 1.e4 Nf6 2.d3 Ne4 3.Nf3?: White could have taken the knight and didn't.
MISSED_KNIGHT = game("e4 Nf6 d3 Ne4 Nf3 Nf6", chess.WHITE)


class TestKinds:
    def test_ignoring_a_threat_that_is_then_carried_out(self):
        records = move_review.review_game(SCHOLAR, SCHOLAR_EVALS, SCHOLAR_THREATS)
        mistake = record(records, 5)
        assert mistake.kind == move_review.MISSED_THREAT
        assert mistake.san == "Nf6" and mistake.best_san == "g6"
        assert mistake.drop == pytest.approx(47.5, abs=0.1)

    def test_a_move_that_hands_the_opponent_material(self):
        records = move_review.review_game(
            DROPPED_KNIGHT,
            evals(6, p3=Eval(cp=30, pv=("d7d5",)), p4=Eval(cp=320, pv=("d3e4",))),
            {3: Eval(cp=40, pv=("b1c3",))},
        )
        assert record(records, 3).kind == move_review.ALLOWED_TACTIC

    def test_not_taking_material_that_was_there(self):
        records = move_review.review_game(
            MISSED_KNIGHT,
            evals(7, p4=Eval(cp=320, pv=("d3e4", "d7d5")), p5=Eval(cp=20, pv=("e4f6",))),
            {4: Eval(cp=330, pv=("e4f6",))},
        )
        assert record(records, 4).kind == move_review.MISSED_TACTIC

    def test_a_loss_with_no_material_involved_is_quiet(self):
        records = move_review.review_game(
            game("h4", chess.WHITE),
            [Eval(cp=30, pv=("e2e4",)), Eval(cp=-200, pv=("e7e5",))],
            # The opponent's reply matches what they'd play anyway, but that
            # move threatened nothing: it isn't a missed threat.
            {0: Eval(cp=-20, pv=("e7e5",))},
        )
        assert record(records, 0).kind == move_review.QUIET

    def test_a_threat_to_win_a_pawn_counts(self):
        # 1.e4 e5 2.Nf3 a6?: the e5 pawn was attacked and is left to fall.
        records = move_review.review_game(
            game("e4 e5 Nf3 a6 Nxe5", chess.BLACK),
            evals(6, p3=Eval(cp=30, pv=("b8c6",)), p4=Eval(cp=150, pv=("f3e5",))),
            {3: Eval(cp=160, pv=("f3e5",))},
        )
        assert record(records, 3).kind == move_review.MISSED_THREAT

    def test_a_strong_move_that_wins_nothing_is_not_a_threat(self):
        """A pawn push can gain a lot positionally; calling it a threat the
        player missed would send them looking for tactics that weren't there."""
        records = move_review.review_game(
            game("h4", chess.WHITE),
            [Eval(cp=30, pv=("e2e4",)), Eval(cp=-200, pv=("e7e5",))],
            {0: Eval(cp=-250, pv=("e7e5",))},
        )
        assert record(records, 0).kind == move_review.QUIET

    def test_a_small_loss_is_not_a_mistake(self):
        records = move_review.review_game(
            game("h4", chess.WHITE), [Eval(cp=30, pv=("e2e4",)), Eval(cp=0, pv=("e7e5",))], {},
        )
        assert record(records, 0).kind is None

    def test_a_drop_from_a_won_position_to_a_still_won_one_is_not_a_mistake(self):
        records = move_review.review_game(
            game("h4", chess.WHITE), [Eval(mate=3, pv=("e2e4",)), Eval(cp=900, pv=("e7e5",))], {},
        )
        assert record(records, 0).kind is None


class TestRecords:
    def test_one_record_per_move_the_player_made(self):
        records = move_review.review_game(SCHOLAR, SCHOLAR_EVALS, SCHOLAR_THREATS)
        assert [r.ply for r in records] == [1, 3, 5]

    def test_phase_is_read_from_the_board(self):
        records = move_review.review_game(SCHOLAR, SCHOLAR_EVALS, SCHOLAR_THREATS)
        assert record(records, 5).phase == "Opening"

    def test_clock_readings(self):
        g = game("h4 e5 a4", chess.WHITE, clocks=(300.0, 300.0, 20.0), initial=300)
        records = move_review.review_game(g, evals(4), {})
        assert record(records, 0).low_clock is False
        last = record(records, 2)
        assert last.seconds_left == 300 and last.seconds_spent == 280
        assert last.low_clock is False

    def test_low_clock_is_under_a_tenth_of_the_start_or_thirty_seconds(self):
        g = game("h4 e5 a4 e4 a5", chess.WHITE, clocks=(300.0, 300.0, 29.0, 300.0, 28.0), initial=300)
        records = move_review.review_game(g, evals(6), {})
        assert record(records, 4).low_clock is True

    def test_without_clocks_nothing_is_low(self):
        records = move_review.review_game(SCHOLAR, SCHOLAR_EVALS, SCHOLAR_THREATS)
        assert all(r.seconds_left is None and not r.low_clock for r in records)


class TestCandidates:
    def test_lists_the_players_mistakes(self):
        assert move_review.candidate_plies(SCHOLAR, SCHOLAR_EVALS) == [5]

    def test_a_mistake_needs_its_threat_check(self):
        with pytest.raises(KeyError):
            move_review.review_game(SCHOLAR, SCHOLAR_EVALS, {})

    def test_no_threat_check_when_in_check(self):
        # 1.e4 f6 2.Qh5+ g6: Black moves out of check, so had no choice of threat to meet.
        g = game("e4 f6 Qh5+ g6", chess.BLACK)
        records = move_review.review_game(
            g, evals(5, p3=Eval(cp=100, pv=("g7g6",)), p4=Eval(cp=600, pv=("h5g6",))), {},
        )
        assert record(records, 3).kind != move_review.MISSED_THREAT

    def test_the_count_of_evals_must_match_the_game(self):
        with pytest.raises(ValueError):
            move_review.review_game(SCHOLAR, SCHOLAR_EVALS[:-1], SCHOLAR_THREATS)
