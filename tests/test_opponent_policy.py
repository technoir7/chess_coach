import chess

from src.opponent.policy import OpponentPolicy


class StubEngine:
    """Stands in for Stockfish so draw logic is testable without a process."""

    def __init__(self, eval_cp):
        self.eval_cp = eval_cp

    def analyze(self, board):
        return {"eval_cp": self.eval_cp, "multipv_lines": []}


def board_with_plies(count: int) -> chess.Board:
    """A legal game of `count` plies, shuffling knights out and back."""
    board = chess.Board()
    cycle = ["Nf3", "Nf6", "Ng1", "Ng8"]
    for i in range(count):
        board.push_san(cycle[i % 4])
    return board


class TestAcceptsDraw:
    def test_declines_in_the_opening_even_when_level(self):
        policy = OpponentPolicy(StubEngine(0))
        assert policy.accepts_draw(board_with_plies(4)) is False

    def test_accepts_when_level_and_past_the_opening(self):
        policy = OpponentPolicy(StubEngine(10))
        assert policy.accepts_draw(board_with_plies(24)) is True

    def test_declines_when_it_is_winning(self):
        policy = OpponentPolicy(StubEngine(400))
        assert policy.accepts_draw(board_with_plies(24)) is False

    def test_declines_when_it_is_losing(self):
        """Symmetry matters: a losing side should not be handed an escape."""
        policy = OpponentPolicy(StubEngine(-400))
        assert policy.accepts_draw(board_with_plies(24)) is False

    def test_missing_evaluation_is_treated_as_level(self):
        """abs(None) used to raise; None now means 'no reason to decline'."""
        policy = OpponentPolicy(StubEngine(None))
        assert policy.accepts_draw(board_with_plies(24)) is True
