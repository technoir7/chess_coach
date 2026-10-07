import chess
import pytest

from src.coach.coach import ChessCoach
from src.utils.config import load_config
from src.utils.paths import repo_path


class CountingEngine:
    """Records how often the coach asks for a fresh search."""

    def __init__(self):
        self.calls = 0

    def analyze(self, board):
        self.calls += 1
        move = next(iter(board.legal_moves))
        return {
            "eval_cp": 35,
            "multipv_lines": [{"pv": [move], "score": None, "depth": 15}],
        }


class SilentIntuition:
    def get_vibe(self, board):
        return {"vibe_score": 0.3}


@pytest.fixture
def coach():
    coach = ChessCoach(load_config(repo_path("system_config.yaml")))
    coach.engine = CountingEngine()
    coach.intuition_engine = SilentIntuition()
    return coach


def test_same_position_is_searched_once(coach):
    """A follow-up question must see the lines the player was already shown,
    not a fresh search that may return a different principal variation."""
    first = coach.build_truth_packet()
    second = coach.build_truth_packet()

    assert coach.engine.calls == 1
    assert first is second


def test_a_new_position_is_searched_again(coach):
    coach.build_truth_packet()
    coach.board.push_san("e4")
    coach.build_truth_packet()

    assert coach.engine.calls == 2


def test_cached_packet_describes_the_position_it_was_built_for(coach):
    packet = coach.build_truth_packet()
    assert packet.fen == chess.Board().fen()
