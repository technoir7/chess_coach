import chess

from src.coach import line_facts


def board_after(*sans: str) -> chess.Board:
    board = chess.Board()
    for san in sans:
        board.push_san(san)
    return board


SICILIAN_D6 = board_after("e4", "c5", "Nf3", "Nc6", "d4", "d6")


class TestChecks:
    def test_identifies_a_checking_move(self):
        """Bb5+ in this line is check - the coach described it as 'attacking
        the Black Bishop', which it is not."""
        facts = line_facts.describe(SICILIAN_D6, ["d5", "Nb8", "h4", "h5", "Bb5+", "Bd7"])
        checks = [m.san for m in facts.moves if m.is_check]
        assert checks == ["Bb5+"]

    def test_no_checks_in_a_quiet_line(self):
        facts = line_facts.describe(SICILIAN_D6, ["c3", "e6", "Bd3", "Nf6"])
        assert not any(m.is_check for m in facts.moves)

    def test_check_is_reported_even_without_the_suffix(self):
        """SAN from elsewhere may omit the + - legality decides, not notation."""
        facts = line_facts.describe(SICILIAN_D6, ["d5", "Nb8", "h4", "h5", "Bb5"])
        assert facts.moves[-1].is_check


class TestCaptures:
    def test_records_what_each_capture_takes(self):
        facts = line_facts.describe(SICILIAN_D6, ["dxc5", "Nf6", "Nc3", "Qa5"])
        captures = [(m.san, m.captured) for m in facts.moves if m.captured]
        assert captures == [("dxc5", "pawn")]

    def test_no_captures_in_a_quiet_line(self):
        facts = line_facts.describe(SICILIAN_D6, ["c3", "e6", "Bd3", "Nf6"])
        assert facts.captured_types == set()

    def test_tracks_multiple_captures(self):
        facts = line_facts.describe(
            SICILIAN_D6, ["dxc5", "Nf6", "Nc3", "Qa5", "Nd2", "Qxc5"]
        )
        assert [m.san for m in facts.moves if m.captured] == ["dxc5", "Qxc5"]
        assert facts.captured_types == {"pawn"}

    def test_queens_are_not_traded_in_that_line(self):
        """The coach claimed this line 'leads to exchanges of Queens'. The
        black queen moves around; no queen is ever captured."""
        facts = line_facts.describe(
            SICILIAN_D6, ["dxc5", "Nf6", "Nc3", "Qa5", "Nd2", "Qxc5", "Nb3", "Qb6"]
        )
        assert "queen" not in facts.captured_types


class TestMaterial:
    def test_even_trade_leaves_material_unchanged(self):
        facts = line_facts.describe(SICILIAN_D6, ["dxc5", "dxc5"])
        assert facts.material_swing == 0

    def test_winning_a_pawn_shows_as_a_swing(self):
        facts = line_facts.describe(SICILIAN_D6, ["dxc5"])
        assert facts.material_swing == 1

    def test_quiet_line_has_no_swing(self):
        facts = line_facts.describe(SICILIAN_D6, ["c3", "e6"])
        assert facts.material_swing == 0


class TestMaterialBalance:
    def test_a_promotion_counts_as_material(self):
        """A reviewer found a line where Black made a queen while the facts
        said White ended up ahead: only captures were being counted."""
        board = chess.Board("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        facts = line_facts.describe(board, ["a8=Q"])
        assert facts.material_swing == 8

    def test_the_balance_after_the_line_is_stated_apart_from_the_gain(self):
        """"White ends up 1 pawn ahead" was read as the final balance when it
        meant the gain over the line; here Black stays far ahead throughout."""
        board = chess.Board("4k3/8/8/3q4/8/8/4p3/4K3 w - - 0 1")
        summary = line_facts.describe(board, ["Kxe2"]).summary()
        assert "White gains 1 point of material" in summary
        assert "afterwards Black is 9 points ahead" in summary

    def test_level_material_is_said_plainly(self):
        summary = line_facts.describe(SICILIAN_D6, ["dxc5", "dxc5"]).summary()
        assert "material is unchanged over the line" in summary
        assert "afterwards material is level" in summary


class TestSummary:
    def test_summary_names_checks_and_captures(self):
        facts = line_facts.describe(SICILIAN_D6, ["dxc5", "Nf6", "Nc3", "Qa5"])
        assert "dxc5 takes a Black pawn" in facts.summary()

    def test_summary_states_absence_plainly(self):
        facts = line_facts.describe(SICILIAN_D6, ["c3", "e6", "Bd3", "Nf6"])
        summary = facts.summary()
        assert "no checks" in summary
        assert "no captures" in summary

    def test_summary_flags_that_queens_survive(self):
        facts = line_facts.describe(
            SICILIAN_D6, ["dxc5", "Nf6", "Nc3", "Qa5", "Nd2", "Qxc5"]
        )
        assert "no queens are exchanged" in facts.summary()


class TestWhoseQueen:
    def test_one_queen_taken_is_not_a_trade(self):
        """From the eval: "the queens are traded" in 31. Qxa7 Qxa7, where only
        White's queen was taken."""
        board = chess.Board("q3k3/8/8/8/8/8/8/Q3K3 w - - 0 1")
        summary = line_facts.describe(board, ["Qxa8+"]).summary()
        assert "only Black's queen is captured, so the queens are not traded" in summary


    def test_both_queens_taken_is_a_trade(self):
        summary = line_facts.describe(SICILIAN_D6, ["dxc5", "dxc5", "Qxd8+", "Kxd8"]).summary()
        assert "both queens are captured, so the queens are traded" in summary


class TestRobustness:
    def test_an_illegal_line_stops_cleanly(self):
        """Never raises on bad input - the caller may pass a model's text."""
        facts = line_facts.describe(SICILIAN_D6, ["d5", "Qxh8"])
        assert [m.san for m in facts.moves] == ["d5"]


def moves(board: chess.Board, *sans: str):
    replay, played = board.copy(), []
    for san in sans:
        played.append(replay.push_san(san))
    return played


class TestWhereALineIsCut:
    """Round 8, p095: the line stopped on ...Nxd5, and playing out only the
    captures on d5 left White a point up. The engine's own line goes Nxd5
    exd5 Rd1: Bxd5 would lose the knight on d4. Where the material settles
    is the engine's call, so the line runs on while the engine keeps
    capturing or checking."""

    def test_runs_on_through_the_engines_captures_and_stops_before_its_first_quiet_move(self):
        pv = moves(chess.Board(), "e4", "d5", "Nc3", "dxe4", "Nxe4", "Nf6")
        assert line_facts.cut(chess.Board(), pv, plies=3, most=20) == 5

    def test_a_quiet_line_is_cut_where_asked(self):
        pv = moves(chess.Board(), "e4", "d5", "Nc3", "Nf6")
        assert line_facts.cut(chess.Board(), pv, plies=2, most=20) == 2

    def test_follows_checks_and_the_answers_to_them(self):
        pv = moves(chess.Board(), "e4", "e5", "Bc4", "Bc5", "Bxf7+", "Kxf7", "Qh5+", "g6", "Qxe5", "d6", "Nf3")
        assert line_facts.cut(chess.Board(), pv, plies=4, most=20) == 9

    def test_a_line_that_runs_out_before_it_settles_needs_more_from_the_engine(self):
        pv = moves(chess.Board(), "e4", "d5", "exd5")
        assert line_facts.cut(chess.Board(), pv, plies=3, most=20) is None

    def test_a_line_ending_the_game_needs_nothing_more(self):
        pv = moves(chess.Board(), "e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#")
        assert line_facts.cut(chess.Board(), pv, plies=7, most=20) == 7

    def test_stops_at_the_most_it_may_show(self):
        pv = moves(chess.Board(), "e4", "d5", "exd5", "Qxd5", "Nc3", "Qxa2")
        assert line_facts.cut(chess.Board(), pv, plies=2, most=4) == 4
