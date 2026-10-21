import chess

from src.coach import threats
from src.coach.threats import detect_threats


class TestNoThreats:
    def test_starting_position_is_quiet(self):
        assert detect_threats(chess.Board(), chess.WHITE) == []
        assert detect_threats(chess.Board(), chess.BLACK) == []

    def test_equal_trade_is_not_a_threat(self):
        """Knight on e5 defended by the d6 pawn, attacked by a bishop.
        Trading bishop for knight wins nothing, so there is nothing to warn about."""
        board = chess.Board("7k/8/3p4/4n3/8/8/1B6/7K b - - 0 1")
        assert detect_threats(board, chess.BLACK) == []

    def test_attacked_piece_that_is_not_ours_is_not_our_problem(self):
        board = chess.Board("7k/8/8/4r3/8/8/1B6/7K b - - 0 1")
        assert detect_threats(board, chess.WHITE) == []


class TestHangingPieces:
    def test_undefended_attacked_piece_is_a_threat(self):
        """Rook on e5 attacked by the b2 bishop with no defender."""
        board = chess.Board("7k/8/8/4r3/8/8/1B6/7K b - - 0 1")
        threats = detect_threats(board, chess.BLACK)
        assert len(threats) == 1
        assert "e5" in threats[0]
        assert "undefended" in threats[0].lower()


class TestUnfavourableExchanges:
    def test_defended_rook_attacked_by_bishop_is_still_a_threat(self):
        """Defended, but the attacker is cheaper - Black loses the exchange."""
        board = chess.Board("7k/8/3p4/4r3/8/8/1B6/7K b - - 0 1")
        threats = detect_threats(board, chess.BLACK)
        assert len(threats) == 1
        assert "e5" in threats[0]


class TestCheck:
    def test_being_in_check_is_a_threat(self):
        board = chess.Board("7k/8/8/8/8/8/8/6KR b - - 0 1")
        threats = detect_threats(board, chess.BLACK)
        assert any("check" in t.lower() for t in threats)

    def test_check_only_counts_for_the_side_to_move(self):
        board = chess.Board("7k/8/8/8/8/8/8/6KR b - - 0 1")
        assert not any("check" in t.lower() for t in detect_threats(board, chess.WHITE))

    def test_king_is_never_reported_as_hanging(self):
        board = chess.Board("7k/8/8/8/8/8/8/6KR b - - 0 1")
        assert not any("King on h8" in t for t in detect_threats(board, chess.BLACK))


class TestThreatsForThePrompt:
    def test_names_the_threatened_piece_and_its_attacker(self):
        """Round 11: "no immediate threat to either side" with Black's d4 pawn
        attacking White's c3 knight - stated only in a list of thirty pieces."""
        board = chess.Board("r1bq1rk1/pp2bppp/3p1n2/2p5/P1BpP3/2NP3P/1PP1QPP1/R1B1K2R w KQ - 0 10")
        text = threats.describe(board)
        assert "- Against White (to move): Knight on c3, attacked by Pawn on d4, which is worth less" in text

    def test_an_undefended_piece_says_so(self):
        board = chess.Board("7k/8/8/4r3/8/8/1B6/7K b - - 0 1")
        assert "- Against Black (to move): Rook on e5, attacked by Bishop on b2, and undefended" in threats.describe(board)

    def test_says_none_for_a_side_with_nothing_under_threat(self):
        text = threats.describe(chess.Board())
        assert "- Against White (to move): none" in text
        assert "- Against Black: none" in text

    def test_a_check_is_a_threat(self):
        board = chess.Board("4k3/8/8/8/8/8/4r3/4K3 w - - 0 1")
        assert "White is in check" in threats.describe(board)
