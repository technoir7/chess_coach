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


def ruy_lopez_board():
    board = chess.Board()
    for san in ("e4", "e5", "Nf3", "Nc6", "Bb5"):
        board.push_san(san)
    return board


def with_rows(text, **rows):
    """The trace with whole rows replaced, keyed by term (King_safety for
    King safety)."""
    lines = text.splitlines()
    for key, row in rows.items():
        term = key.replace("_", " ")
        lines = [row if line.startswith("|") and line[1:13].strip() == term else line for line in lines]
    return "\n".join(lines)


# Stockfish 16's `eval` with White a queen and two rooks up: it stops scoring
# after material and pawns.
LOPSIDED = """\
|   Material |  ----  ---- |  ----  ---- | 17.77 19.10 |
|  Imbalance |  ----  ---- |  ----  ---- |  0.46  0.45 |
|      Pawns |  0.13 -0.02 |  0.13 -0.02 |  0.00  0.00 |
|    Knights |  0.00  0.00 |  0.00  0.00 |  0.00  0.00 |
|    Bishops |  0.00  0.00 |  0.00  0.00 |  0.00  0.00 |
|      Rooks |  0.00  0.00 |  0.00  0.00 |  0.00  0.00 |
|     Queens |  0.00  0.00 |  0.00  0.00 |  0.00  0.00 |
|   Mobility |  0.00  0.00 |  0.00  0.00 |  0.00  0.00 |
|King safety |  0.00  0.00 |  0.00  0.00 |  0.00  0.00 |
|    Threats |  0.00  0.00 |  0.00  0.00 |  0.00  0.00 |
|     Passed |  0.00  0.00 |  0.00  0.00 |  0.00  0.00 |
|      Space |  0.00  0.00 |  0.00  0.00 |  0.00  0.00 |
|   Winnable |  ----  ---- |  ----  ---- |  0.00 -8.22 |
|      Total |  ----  ---- |  ----  ---- | 18.23 11.33 |
Final evaluation       +7.95 (white side)
"""


class TestReadingTheTable:
    def test_each_side_gets_its_own_score_per_factor(self):
        board = ruy_lopez_board()
        factors = classical.parse_trace(RUY_LOPEZ, board)
        p = classical.phase(board)
        assert factors["Mobility"] == pytest.approx(((-0.11 * p - 0.07 * (128 - p)) / 128, (0.01 * p + 0.04 * (128 - p)) / 128))

    def test_middlegame_and_endgame_scores_are_blended_by_phase(self):
        board = chess.Board("4k3/pppp1ppp/8/8/8/2N5/PPPPQPPP/R3K2R w KQ - 0 1")
        p = classical.phase(board)
        assert 0 < p < classical.PHASE_MIDGAME
        white, black = classical.parse_trace(RUY_LOPEZ, board)["Bishops"]
        assert white == pytest.approx((-0.20 * p + -0.76 * (128 - p)) / 128)
        assert black == pytest.approx((-0.10 * p + -0.58 * (128 - p)) / 128)

    def test_leaves_out_material_and_threats(self):
        """Material is counted elsewhere, and threats are tactics."""
        factors = classical.parse_trace(RUY_LOPEZ, ruy_lopez_board())
        assert set(factors) == {
            "Pawns", "Knights", "Bishops", "Rooks", "Queens",
            "Mobility", "King safety", "Passed", "Space",
        }

    def test_gives_nothing_for_a_side_in_check(self):
        assert classical.parse_trace("Final evaluation: none (in check)", chess.Board()) is None

    def test_an_unreadable_trace_is_an_error(self):
        with pytest.raises(ValueError):
            classical.parse_trace("Final evaluation       +0.06 (white side)", chess.Board())


class TestWhatStockfishDidNotScore:
    """Its zeros there are not readings: round 7's prompts showed them as
    "about even" with one side a queen up."""

    def test_far_ahead_in_material_only_the_pawns_are_scored(self):
        board = chess.Board("4k3/pppp1ppp/8/8/8/2N5/PPPPQPPP/R3K2R w KQ - 0 1")
        assert set(classical.parse_trace(LOPSIDED, board)) == {"Pawns"}

    def test_a_little_less_far_ahead_space_is_not_scored(self):
        trace = with_rows(
            RUY_LOPEZ,
            Material="|   Material |  ----  ---- |  ----  ---- |  3.00  3.00 |",
            Mobility="|   Mobility |  0.60  0.60 | -0.40 -0.40 |  1.00  1.00 |",
        )
        factors = classical.parse_trace(trace, chess.Board())
        assert "Space" not in factors and "Mobility" in factors

    def test_an_ending_with_its_own_rule_scores_nothing(self):
        trace = with_rows(LOPSIDED, Material="|   Material |  ----  ---- |  ----  ---- |  0.00  0.00 |",
                          Imbalance="|  Imbalance |  ----  ---- |  ----  ---- |  0.00  0.00 |",
                          Pawns="|      Pawns |  0.00  0.00 |  0.00  0.00 |  0.00  0.00 |")
        assert classical.parse_trace(trace, chess.Board("8/8/4k3/8/8/2Q5/8/4K3 w - - 0 1")) == {}


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
