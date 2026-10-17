import chess

from src.coach import claims


def board_after(*sans: str) -> chess.Board:
    board = chess.Board()
    for san in sans:
        board.push_san(san)
    return board


def claim(what, holds=True, at="current", sentence=1, **args):
    return {"sentence": sentence, "at": at, "kind": what, "args": args, "holds": holds}


def false_claims(board, made, lines=()):
    return claims.check(board, list(lines), made).false


ITALIAN = board_after("e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5")


class TestPositionsInsideLines:
    def test_castling_does_not_connect_rooks_with_a_piece_between(self):
        """From rounds 4 and 5: "castles and connects the rooks" with the c1
        bishop and the queen still between them."""
        made = [claim("connected_rooks", side="White", at={"line": "O-O", "after": "4. O-O"}, sentence=3)]
        [finding] = false_claims(ITALIAN, made, [["O-O", "Nf6"]])
        assert finding.sentence == 3
        assert "Bishop on c1" in finding.truth

    def test_a_position_can_be_named_by_its_move_alone(self):
        made = [claim("connected_rooks", side="White", at={"line": "O-O", "after": "O-O"})]
        assert len(false_claims(ITALIAN, made, [["O-O", "Nf6"]])) == 1

    def test_a_position_that_cannot_be_found_is_left_unchecked(self):
        made = [claim("connected_rooks", side="White", at={"line": "Qxf7", "after": "Qxf7"})]
        result = claims.check(ITALIAN, [["O-O", "Nf6"]], made)
        assert result.false == [] and len(result.unchecked) == 1


class TestKinds:
    def test_connected_rooks_with_nothing_between(self):
        board = chess.Board("4k3/8/8/8/8/8/8/R4RK1 w - - 0 1")
        assert false_claims(board, [claim("connected_rooks", side="White")]) == []

    def test_a_pawn_pinned_along_its_file_can_still_move(self):
        """From round 5: "pins the e4 pawn to the king, so that pawn can't move"."""
        board = chess.Board("4k3/4q3/8/8/4P3/8/4K3/8 w - - 0 1")
        [finding] = false_claims(board, [claim("can_move", holds=False, square="e4")])
        assert "e5" in finding.truth

    def test_a_reply_with_other_legal_moves_is_not_forced(self):
        board = board_after("e4", "e5", "Bc4", "Nc6")
        made = [claim("forced", at={"line": "Bxf7+", "after": "3. Bxf7+"})]
        assert len(false_claims(board, made, [["Bxf7+", "Kxf7"]])) == 1

    def test_a_defended_piece_is_not_loose(self):
        """From round 4: "the knight on a3 is loose" with the b2 pawn guarding it."""
        board = chess.Board("4k3/8/8/8/8/N7/1P6/4K3 w - - 0 1")
        [finding] = false_claims(board, [claim("defended", holds=False, square="a3")])
        assert "Pawn on b2" in finding.truth

    def test_a_denied_pin_that_exists(self):
        """From round 5: 8. Bg5 "pins nothing" with the queen behind the f6 knight."""
        board = board_after("d4", "Nf6", "c4", "e6", "Nc3", "d5", "Bg5")
        assert len(false_claims(board, [claim("pinned", holds=False, square="f6")])) == 1

    def test_an_attack_the_piece_cannot_make(self):
        """From round 4: "the knight on b3 defends the rook on a3"."""
        board = chess.Board("4k3/8/8/8/8/RN6/8/4K3 w - - 0 1")
        assert len(false_claims(board, [claim("defends", piece="b3", target="a3")])) == 1
        assert false_claims(board, [claim("defends", piece="b3", target="a3", holds=False)]) == []

    def test_attacks_means_an_enemy_piece_or_an_empty_square(self):
        board = board_after("e4", "e5", "Nf3")
        assert false_claims(board, [claim("attacks", piece="f3", target="e5")]) == []
        assert len(false_claims(board, [claim("attacks", piece="f3", target="d4")])) == 0
        assert len(false_claims(board, [claim("attacks", piece="f3", target="e4")])) == 1

    def test_a_minor_piece_still_at_home(self):
        """From round 4: Nbd2 "develops the last minor piece", f1 bishop at home."""
        board = board_after("d4", "d5", "Nf3", "Nf6", "Bf4", "e6")
        made = [claim("all_minor_pieces_developed", side="White", at={"line": "Nbd2", "after": "Nbd2"})]
        [finding] = false_claims(board, made, [["Nbd2"]])
        assert "Bishop on f1" in finding.truth

    def test_material(self):
        board = chess.Board("4k3/8/8/3b4/8/8/8/4K3 w - - 0 1")
        assert len(false_claims(board, [claim("material", leader="level")])) == 1
        assert false_claims(board, [claim("material", leader="Black")]) == []

    def test_pawn_structure(self):
        board = chess.Board("4k3/2p5/8/8/3P4/8/8/4K3 w - - 0 1")
        assert len(false_claims(board, [claim("pawn", square="c7", kind="doubled")])) == 1
        assert false_claims(board, [claim("pawn", square="d4", kind="isolated")]) == []
        assert len(false_claims(board, [claim("pawn", square="d4", kind="passed")])) == 1

    def test_open_file(self):
        board = chess.Board("4k3/2p5/8/8/3P4/8/8/4K3 w - - 0 1")
        assert false_claims(board, [claim("open_file", file="e")]) == []
        assert len(false_claims(board, [claim("open_file", file="d")])) == 1

    def test_piece_on(self):
        board = board_after("e4")
        assert len(false_claims(board, [claim("piece_on", square="c1", piece="knight", side="White")])) == 1
        assert false_claims(board, [claim("piece_on", square="c1", piece="bishop", side="White")]) == []

    def test_check(self):
        board = board_after("e4", "e5", "Bc4", "Nc6")
        assert false_claims(board, [claim("check", move="Bxf7")]) == []
        assert len(false_claims(board, [claim("check", move="Qh5")])) == 1

    def test_a_claim_about_an_empty_square_is_false(self):
        board = chess.Board()
        [finding] = false_claims(board, [claim("defended", square="e4")])
        assert "no piece on e4" in finding.truth

    def test_an_unknown_kind_is_left_unchecked(self):
        result = claims.check(chess.Board(), [], [claim("outpost", square="d5")])
        assert result.false == [] and len(result.unchecked) == 1
