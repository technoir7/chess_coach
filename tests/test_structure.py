import chess

from src.coach import structure


def board_after(*sans: str) -> chess.Board:
    board = chess.Board()
    for san in sans:
        board.push_san(san)
    return board


class TestMaterial:
    def test_counts_each_sides_pieces(self):
        text = structure.describe(chess.Board())
        assert "White has Queen, 2 Rooks, 2 Bishops, 2 Knights, 8 Pawns" in text
        assert "material is level" in text

    def test_says_who_is_ahead_and_by_how_much(self):
        """From the eval: "material is level" with Black a bishop up."""
        board = chess.Board("4k3/8/8/3b4/8/8/8/4K3 w - - 0 1")
        assert "Black is 3 points ahead" in structure.describe(board)


class TestPawns:
    def test_doubled_pawns_need_two_on_one_file(self):
        """From the eval: "Black has doubled c-pawns" with one c-pawn."""
        single = chess.Board("4k3/2p5/8/8/8/8/8/4K3 w - - 0 1")
        assert "Black doubled pawns: none" in structure.describe(single)
        doubled = chess.Board("4k3/2p5/2p5/8/8/8/8/4K3 w - - 0 1")
        assert "Black doubled pawns: c-file (c7, c6)" in structure.describe(doubled)

    def test_an_isolated_pawn_has_no_friend_on_either_side_file(self):
        board = chess.Board("4k3/8/8/8/3P4/8/PP6/4K3 w - - 0 1")
        text = structure.describe(board)
        assert "White isolated pawns: d4" in text
        assert "White isolated pawns: a2" not in text

    def test_a_passed_pawn_has_no_enemy_pawn_ahead_on_its_own_or_side_files(self):
        board = chess.Board("4k3/6p1/8/P7/8/8/7P/4K3 w - - 0 1")
        text = structure.describe(board)
        assert "White passed pawns: a5" in text
        assert "h2" not in text.split("White passed pawns:")[1].splitlines()[0]

    def test_names_open_files(self):
        board = board_after("e4", "d5", "exd5", "Qxd5", "d4", "e5", "dxe5", "Qxd1+", "Kxd1")
        assert "Open files (no pawns): d\n" in structure.describe(board) + "\n"
        assert "Open files (no pawns): none" in structure.describe(board_after("e4", "d5", "exd5", "Qxd5"))


def candidates(text, side):
    line = next(l for l in text.splitlines() if l.startswith(f"- {side} candidate passed pawns"))
    return line.rsplit(": ", 1)[1]


class TestCandidatePassedPawns:
    """Stockfish 16's passed-pawn score also counts pawns that are not passed
    yet but whose way can be cleared. Round 7's prompts showed that score
    favouring a side whose passed pawns were listed as none."""

    def test_a_pawn_whose_only_stopper_it_can_take_now(self):
        text = structure.describe(chess.Board("4k3/8/3p4/4P3/8/8/8/4K3 w - - 0 1"))
        assert candidates(text, "White") == "e5"
        assert "White passed pawns: none" in text

    def test_a_pawn_whose_stoppers_its_neighbours_outnumber(self):
        text = structure.describe(chess.Board("4k3/8/5p2/8/3PP3/8/8/4K3 w - - 0 1"))
        assert "White passed pawns: d4" in text
        assert candidates(text, "White") == "e4"
        assert candidates(text, "Black") == "none"

    def test_without_the_neighbour_it_is_not_a_candidate(self):
        text = structure.describe(chess.Board("4k3/8/5p2/8/4P3/8/8/4K3 w - - 0 1"))
        assert candidates(text, "White") == "none"

    def test_an_advanced_blocked_pawn_a_neighbour_can_help_through(self):
        text = structure.describe(chess.Board("4k3/8/4p3/4P3/3P4/8/8/4K3 w - - 0 1"))
        assert candidates(text, "White") == "e5"

    def test_a_blocked_pawn_not_yet_on_the_fifth_rank_is_not_a_candidate(self):
        text = structure.describe(chess.Board("4k3/8/8/4p3/4P3/3P4/8/4K3 w - - 0 1"))
        assert candidates(text, "White") == "none"


class TestOutposts:
    def test_a_square_a_pawn_defends_and_no_enemy_pawn_can_attack(self):
        board = chess.Board("4k3/8/8/8/4P3/8/8/4K3 w - - 0 1")
        line = next(l for l in structure.describe(board).splitlines() if "White outposts" in l)
        assert line.endswith(": d5, f5")

    def test_not_an_outpost_while_an_enemy_pawn_can_still_advance_to_attack_it(self):
        """Round 11: "the e5 outpost" with Black's f7 pawn able to come to f6."""
        board = chess.Board("rn1q1rk1/pppb1pbp/4pnp1/3p4/3P3N/P3P3/1PPNBPPP/R1BQ1RK1 w - - 2 9")
        line = next(l for l in structure.describe(board).splitlines() if "White outposts" in l)
        assert line.endswith(": none")

    def test_a_pawn_that_has_gone_past_cannot_come_back(self):
        board = chess.Board("4k3/8/8/8/4P3/5p2/8/4K3 w - - 0 1")
        line = next(l for l in structure.describe(board).splitlines() if "White outposts" in l)
        assert line.endswith(": d5, f5")

    def test_names_a_piece_standing_on_an_outpost(self):
        board = chess.Board("4k3/8/8/3N4/4P3/8/8/4K3 w - - 0 1")
        line = next(l for l in structure.describe(board).splitlines() if "White outposts" in l)
        assert line.endswith(": d5 (Knight on it), f5")

    def test_black_outposts_are_on_its_own_fourth_to_sixth_ranks(self):
        board = chess.Board("4k3/8/8/4p3/8/8/8/4K3 w - - 0 1")
        line = next(l for l in structure.describe(board).splitlines() if "Black outposts" in l)
        assert line.endswith(": d4, f4")
