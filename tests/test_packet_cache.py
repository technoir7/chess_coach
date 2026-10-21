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

    def search_line(self, board):
        return []


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


class RecordingClassical:
    """Stands in for Stockfish 16, scoring each position by its FEN."""

    def __init__(self):
        self.seen = []

    def factors(self, board):
        self.seen.append(board.fen())
        return {"Space": (len(self.seen), 0.0)}


def test_the_packet_carries_positional_factors_now_and_at_each_line_end(coach):
    coach.classical_engine = RecordingClassical()
    packet = coach.build_truth_packet()

    line = packet.candidate_lines[0]
    end = chess.Board()
    for san in line.line_san:
        end.push_san(san)
    assert coach.classical_engine.seen == [chess.Board().fen(), end.fen()]
    assert packet.factors == {"Space": (1, 0.0)}
    assert line.factors_after == {"Space": (2, 0.0)}


def test_without_stockfish_16_there_are_no_factors(coach):
    packet = coach.build_truth_packet()
    assert packet.factors is None
    assert packet.candidate_lines[0].factors_after is None


class CapturingEngine:
    """Its line stops on a capture; asked to go on, it takes back and then
    plays a quiet move."""

    def __init__(self):
        self.continued_from = []

    def analyze(self, board):
        return {"eval_cp": 0, "multipv_lines": [{"pv": [chess.Move.from_uci("e4d5")], "score": None}]}

    def search_line(self, board):
        self.continued_from.append(board.fen())
        return [chess.Move.from_uci("d8d5"), chess.Move.from_uci("b1c3")]


def test_a_line_that_runs_out_mid_exchange_is_continued_by_the_engine(coach):
    coach.engine = CapturingEngine()
    coach.board = chess.Board()
    for san in ("e4", "d5"):
        coach.board.push_san(san)
    coach.LINE_PLIES = 1
    packet = coach.build_truth_packet()

    assert packet.candidate_lines[0].line_san == ["exd5", "Qxd5"]
    assert len(coach.engine.continued_from) == 1
