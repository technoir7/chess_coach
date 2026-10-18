import chess

from src.coach import relations


def board_after(*sans: str) -> chess.Board:
    board = chess.Board()
    for san in sans:
        board.push_san(san)
    return board


def line_for(board: chess.Board, description: str) -> str:
    """The relations line that starts with e.g. "White Bishop on f3"."""
    for line in relations.describe(board).splitlines():
        if line.startswith(f"- {description}:"):
            return line
    raise AssertionError(f"no line for {description}")


class TestAttacksAndDefends:
    def test_a_bishop_never_defends_a_square_of_the_other_colour(self):
        """From the eval: "Bf3 adds protection to d4", a dark square."""
        board = chess.Board("4k3/8/8/8/3P4/5B2/8/4K3 w - - 0 1")
        assert "d4" not in line_for(board, "White Bishop on f3")

    def test_a_rook_does_not_defend_through_its_own_piece(self):
        """From the eval: "Re1 supports the e4 pawn" with a bishop on e3."""
        board = chess.Board("4k3/8/8/8/4P3/4B3/8/4RK2 w - - 0 1")
        line = line_for(board, "White Rook on e1")
        assert "defends Bishop on e3" in line
        assert "e4" not in line

    def test_names_the_enemy_pieces_a_piece_attacks(self):
        board = board_after("e4", "e5", "Nf3", "Nc6")
        assert "attacks Pawn on e5" in line_for(board, "White Knight on f3")

    def test_says_so_when_a_piece_attacks_and_defends_nothing(self):
        line = line_for(chess.Board(), "White Knight on b1")
        assert "attacks nothing" in line


class TestPins:
    def test_a_bishop_pins_a_knight_to_the_queen_behind_it(self):
        board = board_after("d4", "Nf6", "c4", "e6", "Nc3", "d5", "Bg5")
        assert "Bishop on g5 pins Black Knight on f6 to the Queen on d8" in relations.describe(board)

    def test_no_pin_when_a_piece_of_equal_value_stands_behind(self):
        """From the eval: "the pin on f6" with e7 blocked or nothing behind."""
        board = board_after("d4", "Nf6", "c4", "e6", "Nc3", "d5", "Bg5", "Be7")
        assert "pins" not in relations.describe(board)

    def test_a_pin_to_the_king_is_said_to_be_absolute(self):
        board = board_after("e4", "e6", "d4", "d5", "Nc3", "Bb4")
        assert (
            "Bishop on b4 pins White Knight on c3 to the King on e1 (it has no legal move)"
            in relations.describe(board)
        )

    def test_no_pin_when_an_own_pawn_shields_the_king(self):
        """From the eval: "Bb4 pins the knight on c3" with the d2 pawn behind it."""
        board = board_after("e4", "e6", "Nc3", "Bb4")
        assert "pins" not in relations.describe(board)


class TestWhatAPinnedPieceCanStillDo:
    def test_a_pawn_pinned_along_its_file_can_still_push(self):
        """Round 5: "pins the e4 pawn to the king, so that pawn can't move"."""
        board = chess.Board("4k3/4q3/8/8/4P3/8/4K3/8 w - - 0 1")
        assert "pins White Pawn on e4 to the King on e2 (its only legal moves: e5)" in relations.describe(board)


class TestOnlyPinsThatCost:
    """Round 7: "Qd8 pins the d4 pawn to the Knight on d2" with d2 defended -
    the pawn could move, since Qxd2 would only lose the queen."""

    def test_no_pin_onto_a_defended_piece_worth_less_than_the_attacker(self):
        board = chess.Board("3qk3/8/8/8/3P4/8/3N4/3QK3 w - - 0 1")
        assert "pins" not in relations.describe(board)

    def test_no_pin_onto_a_defended_piece_worth_the_same(self):
        board = chess.Board("4k3/4r3/8/8/4P3/8/4R3/5K2 w - - 0 1")
        assert "pins" not in relations.describe(board)

    def test_a_pin_onto_an_undefended_piece_stands(self):
        board = chess.Board("3qk3/8/8/8/3P4/8/3N4/4K3 w - - 0 1")
        board.remove_piece_at(chess.E1)
        board.set_piece_at(chess.H1, chess.Piece(chess.KING, chess.WHITE))
        assert "Queen on d8 pins White Pawn on d4 to the Knight on d2" in relations.describe(board)

    def test_a_pin_onto_a_piece_worth_more_than_the_attacker_stands(self):
        board = chess.Board("4k3/8/8/1b6/8/3N4/8/5QK1 w - - 0 1")
        assert board.is_attacked_by(chess.WHITE, chess.F1)
        assert "Bishop on b5 pins White Knight on d3 to the Queen on f1" in relations.describe(board)
