import shutil

import chess
import pytest

from src.engine import classical

# Stockfish 16's `eval` after 1. e4 e5 2. Nf3 Nc6 3. Bb5, trimmed to the table.
RUY_LOPEZ = """\
 Contributing terms for the classical eval:
+------------+-------------+-------------+-------------+
|    Term    |    White    |    Black    |    Total    |
|            |   MG    EG  |   MG    EG  |   MG    EG  |
+------------+-------------+-------------+-------------+
|   Material |  ----  ---- |  ----  ---- |  0.08  0.08 |
|  Imbalance |  ----  ---- |  ----  ---- |  0.00  0.00 |
|      Pawns |  0.13 -0.02 |  0.13 -0.02 |  0.00  0.00 |
|    Knights | -0.08 -0.13 | -0.05 -0.10 | -0.03 -0.03 |
|    Bishops | -0.20 -0.76 | -0.10 -0.58 | -0.09 -0.18 |
|      Rooks | -0.17 -0.04 | -0.17 -0.04 |  0.00  0.00 |
|     Queens |  0.00  0.00 |  0.00  0.00 |  0.00  0.00 |
|   Mobility | -0.11 -0.07 |  0.01  0.04 | -0.11 -0.12 |
|King safety |  0.46 -0.07 |  0.43 -0.07 |  0.02  0.00 |
|    Threats |  0.29  0.35 |  0.26  0.25 |  0.03  0.10 |
|     Passed |  0.00  0.00 |  0.00  0.00 |  0.00  0.00 |
|      Space |  0.34  0.00 |  0.34  0.00 |  0.00  0.00 |
|   Winnable |  ----  ---- |  ----  ---- |  0.00 -0.12 |
+------------+-------------+-------------+-------------+
|      Total |  ----  ---- |  ----  ---- | -0.10 -0.27 |
+------------+-------------+-------------+-------------+

Classical evaluation   -0.10 (white side)
Final evaluation       +0.06 (white side) [with scaled NNUE, hybrid, ...]
"""


class TestReadingTheTable:
    def test_each_side_gets_its_own_score_per_factor(self):
        factors = classical.parse_trace(RUY_LOPEZ, phase=classical.PHASE_MIDGAME)
        assert factors["Mobility"] == (-0.11, 0.01)
        assert factors["Space"] == (0.34, 0.34)

    def test_middlegame_and_endgame_scores_are_blended_by_phase(self):
        factors = classical.parse_trace(RUY_LOPEZ, phase=classical.PHASE_MIDGAME // 2)
        white, black = factors["Bishops"]
        assert white == pytest.approx((-0.20 + -0.76) / 2)
        assert black == pytest.approx((-0.10 + -0.58) / 2)

    def test_leaves_out_material_and_threats(self):
        """Material is counted elsewhere, and threats are tactics."""
        factors = classical.parse_trace(RUY_LOPEZ, phase=classical.PHASE_MIDGAME)
        assert set(factors) == {
            "Pawns", "Knights", "Bishops", "Rooks", "Queens",
            "Mobility", "King safety", "Passed", "Space",
        }

    def test_gives_nothing_for_a_side_in_check(self):
        assert classical.parse_trace("Final evaluation: none (in check)", phase=64) is None

    def test_an_unreadable_trace_is_an_error(self):
        with pytest.raises(ValueError):
            classical.parse_trace("Final evaluation       +0.06 (white side)", phase=64)


class TestPhase:
    def test_the_starting_position_is_all_middlegame(self):
        assert classical.phase(chess.Board()) == classical.PHASE_MIDGAME

    def test_kings_and_pawns_are_all_endgame(self):
        assert classical.phase(chess.Board("4k3/pppp4/8/8/8/8/PPPP4/4K3 w - - 0 1")) == 0


@pytest.mark.skipif(shutil.which("stockfish16") is None, reason="Stockfish 16 not installed")
class TestTheRealEngine:
    def test_the_starting_position_is_the_same_for_both_sides(self):
        engine = classical.ClassicalEngine("stockfish16")
        engine.start()
        try:
            factors = engine.factors(chess.Board())
        finally:
            engine.stop()
        assert all(white == black for white, black in factors.values())

    def test_a_position_in_check_has_no_factors(self):
        engine = classical.ClassicalEngine("stockfish16")
        engine.start()
        try:
            assert engine.factors(chess.Board("4k3/8/8/8/8/8/4q3/4K3 w - - 0 1")) is None
            # and the engine is still in step for the next position
            assert engine.factors(chess.Board()) is not None
        finally:
            engine.stop()
