import chess
import pytest

from src.games.win_chances import Eval, win_percent


class TestWinPercent:
    def test_level_is_fifty(self):
        assert win_percent(Eval(cp=0), chess.WHITE) == 50

    def test_matches_lichess_curve(self):
        # Lichess: 50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1)
        assert win_percent(Eval(cp=100), chess.WHITE) == pytest.approx(59.1, abs=0.1)
        assert win_percent(Eval(cp=300), chess.WHITE) == pytest.approx(75.2, abs=0.1)

    def test_is_from_the_given_side(self):
        assert win_percent(Eval(cp=300), chess.BLACK) == pytest.approx(100 - 75.2, abs=0.1)

    def test_big_scores_are_capped(self):
        assert win_percent(Eval(cp=5000), chess.WHITE) == win_percent(Eval(cp=1000), chess.WHITE)

    def test_a_mate_counts_as_the_cap(self):
        assert win_percent(Eval(mate=3), chess.WHITE) == win_percent(Eval(cp=1000), chess.WHITE)
        assert win_percent(Eval(mate=-2), chess.WHITE) == win_percent(Eval(cp=-1000), chess.WHITE)

    def test_an_eval_needs_a_score(self):
        with pytest.raises(ValueError):
            Eval()
