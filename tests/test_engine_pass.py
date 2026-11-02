import shutil

import chess
import pytest

from src.games import engine_pass
from src.games.win_chances import Eval

needs_stockfish = pytest.mark.skipif(shutil.which("stockfish") is None, reason="Stockfish not installed")


class TestTerminal:
    def test_checkmate_is_scored_without_an_engine(self):
        board = chess.Board()
        for san in "f3 e5 g4 Qh4#".split():
            board.push_san(san)
        assert engine_pass.terminal_eval(board) == Eval(mate=-1)

    def test_stalemate_is_level(self):
        board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        assert engine_pass.terminal_eval(board) == Eval(cp=0)

    def test_a_live_position_is_not_terminal(self):
        assert engine_pass.terminal_eval(chess.Board()) is None


class TestThreatPosition:
    def test_passes_the_move_to_the_opponent(self):
        board = chess.Board()
        board.push_san("e4")
        fen = engine_pass.threat_fen(board)
        assert chess.Board(fen).turn == chess.WHITE
        assert chess.Board(fen).ep_square is None


class TestCache:
    def test_round_trip(self, tmp_path):
        path = tmp_path / "evals.jsonl"
        cache = engine_pass.EvalCache(path, depth=16)
        cache.put("fen a", Eval(cp=12, pv=("e2e4",)))
        cache.put("fen b", Eval(mate=-3))
        cache.save()
        again = engine_pass.EvalCache(path, depth=16)
        assert again.get("fen a") == Eval(cp=12, pv=("e2e4",))
        assert again.get("fen b") == Eval(mate=-3)

    def test_a_different_depth_is_a_different_entry(self, tmp_path):
        path = tmp_path / "evals.jsonl"
        cache = engine_pass.EvalCache(path, depth=16)
        cache.put("fen a", Eval(cp=12))
        cache.save()
        assert engine_pass.EvalCache(path, depth=12).get("fen a") is None


@needs_stockfish
class TestStockfish:
    def test_finds_a_mate_in_one(self):
        # White to move: Qxf7#.
        board = chess.Board()
        for san in "e4 e5 Bc4 Nc6 Qh5 Nf6".split():
            board.push_san(san)
        [result] = engine_pass.evaluate([board.fen()], depth=10, workers=1)
        assert result.mate == 1 and result.pv[0] == "h5f7"

    def test_reads_a_threat_position(self):
        board = chess.Board()
        for san in "e4 e5 Bc4 Nc6 Qh5".split():
            board.push_san(san)
        [result] = engine_pass.evaluate([engine_pass.threat_fen(board)], depth=10, workers=1)
        assert result.mate == 1 and result.pv[0] == "h5f7"

    def test_second_best_is_another_move(self, tmp_path):
        board = chess.Board()
        for san in "e4 e5 Bc4 Nc6 Qh5 Nf6".split():
            board.push_san(san)
        cache = engine_pass.EvalCache(tmp_path / "second.jsonl", depth=10)
        [second] = engine_pass.second_bests([board.fen()], cache, workers=1)
        assert second.pv[0] != "h5f7" and second.mate is None
        assert engine_pass.EvalCache(tmp_path / "second.jsonl", depth=10).get(board.fen()) == second
