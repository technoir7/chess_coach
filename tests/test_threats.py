import chess

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
