import chess

from src.coach import walkthrough


def board_after(*sans: str) -> chess.Board:
    board = chess.Board()
    for san in sans:
        board.push_san(san)
    return board


class TestMoveByMove:
    def test_says_what_the_moved_piece_does_on_its_new_square(self):
        """From the eval: "pushes the Bishop back to c7, ending its pressure on
        g3" - the bishop on c7 still reached g3. Each move's piece is read off
        the board it lands on."""
        text = walkthrough.describe(board_after("e4", "e5"), ["Nf3", "Nc6"])
        assert "2. Nf3: White Knight on f3 attacks Pawn on e5" in text
        assert "2... Nc6: Black Knight on c6 attacks nothing; defends Pawn on e5" in text

    def test_a_reply_with_other_legal_moves_is_not_forced(self):
        """From the eval: "the check forces the King to f8" when Ke7, Rd7 and
        Qd7 were also legal."""
        board = board_after("e4", "e5", "Bc4", "Nc6")
        text = walkthrough.describe(board, ["Bxf7+", "Kxf7"])
        assert "Black then has 1 legal move, so its reply is forced" not in text
        assert "Black then has 2 legal moves, so its reply is not forced" in text

    def test_a_single_legal_reply_is_forced(self):
        board = chess.Board("k7/8/1K6/8/8/8/8/7R w - - 0 1")
        text = walkthrough.describe(board, ["Rh7"])
        assert "Black then has 1 legal move, so its reply is forced" in text

    def test_castling_describes_the_rook_too(self):
        """From the eval: "castles and connects the rooks" with the c1 bishop
        still between them."""
        board = board_after("e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5")
        text = walkthrough.describe(board, ["O-O"])
        assert "White Rook on f1" in text.split("O-O:")[1].splitlines()[0]


class TestEndOfLine:
    def test_gives_relations_and_material_for_the_final_position(self):
        board = board_after("e4", "d5", "exd5", "Qxd5", "d4", "e5")
        text = walkthrough.describe(board, ["dxe5", "Qxd1+", "Kxd1"])
        end = text.split("POSITION AT THE END OF THIS LINE")[1]
        assert "White King on d1" in end
        assert "White is 1 pawn ahead" in end
        assert "Open files (no pawns): d" in end
