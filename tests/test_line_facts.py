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


class TestSummary:
    def test_summary_names_checks_and_captures(self):
        facts = line_facts.describe(SICILIAN_D6, ["dxc5", "Nf6", "Nc3", "Qa5"])
        assert "dxc5 takes a pawn" in facts.summary()

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


class TestRobustness:
    def test_an_illegal_line_stops_cleanly(self):
        """Never raises on bad input - the caller may pass a model's text."""
        facts = line_facts.describe(SICILIAN_D6, ["d5", "Qxh8"])
        assert [m.san for m in facts.moves] == ["d5"]
