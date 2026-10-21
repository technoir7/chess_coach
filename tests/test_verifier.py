import chess

from src.coach import verifier


def board_after(*sans: str) -> chess.Board:
    board = chess.Board()
    for san in sans:
        board.push_san(san)
    return board


SICILIAN = board_after("e4", "c5")
SICILIAN_D6 = board_after("e4", "c5", "Nf3", "Nc6", "d4", "d6")


class TestIllegalMoveDetection:
    def test_flags_a_move_that_is_not_legal_here(self):
        """Bxb5 was the exact bait move during manual testing."""
        assert verifier.find_illegal_moves("You could try Bxb5 here.", SICILIAN) == ["Bxb5"]

    def test_accepts_legal_moves(self):
        assert verifier.find_illegal_moves("Nf3 develops and controls d4.", SICILIAN) == []

    def test_flags_only_the_illegal_one_in_a_mixed_sentence(self):
        text = "Nf3 is good, but Qxd8 is not available."
        assert verifier.find_illegal_moves(text, SICILIAN) == ["Qxd8"]

    def test_square_references_are_not_treated_as_moves(self):
        """Prose about squares must not trip the verifier - 'the pawn on e5'
        is a description, not a claimed move."""
        text = "Black's pawn on c5 fights for d4, and the e4 pawn holds the centre."
        assert verifier.find_illegal_moves(text, SICILIAN) == []

    def test_opponent_replies_are_verifiable_claims(self):
        """White is to move, but 'Black can answer Nc6' is checkable against the
        position and must not be rejected as an invention."""
        assert verifier.find_illegal_moves("Black can answer Nc6.", SICILIAN) == []

    def test_naming_a_piece_by_its_square_is_not_a_move(self):
        """From the eval: "supported by Nc3, Nf3, Bd3" and "White's Qc3 and
        Black's Qa5" name pieces where they stand. A piece cannot move to a
        square it already occupies, so these are never move claims."""
        text = "White's Nf3 eyes d4, and Black's Nc6 answers it."
        assert verifier.find_illegal_moves(text, SICILIAN_D6) == []

    def test_a_capture_onto_an_occupied_square_is_still_a_move(self):
        assert verifier.find_illegal_moves("Nxc6 wins a piece.", SICILIAN_D6) == ["Nxc6"]

    def test_a_move_available_to_neither_side_is_still_flagged(self):
        assert verifier.find_illegal_moves("White plays Ra6.", SICILIAN) == ["Ra6"]

    def test_castling_is_understood(self):
        assert verifier.find_illegal_moves("White should play O-O soon.", SICILIAN) == ["O-O"]

    def test_check_and_mate_suffixes_are_stripped(self):
        board = board_after("e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6")
        assert verifier.find_illegal_moves("Then Qxf7# ends it.", board) == []


class TestVariationDetection:
    def test_flags_a_line_with_nothing_to_quote_from(self):
        """With no searched lines supplied, any sequence means it calculated."""
        text = "After 1. Bxb5 Qxb5 2. Bxd7+ Kxd7 White wins."
        assert verifier.find_unsanctioned_lines(text) != []

    def test_numbered_prose_is_not_a_variation(self):
        text = "1. Develop your pieces. 2. Castle early. 3. Connect the rooks."
        assert verifier.find_unsanctioned_lines(text) == []

    def test_naming_a_single_move_is_not_a_variation(self):
        assert verifier.find_unsanctioned_lines("The engine prefers Nf3 here.") == []


SANCTIONED = [
    ["Nf3", "Nc6", "d4", "cxd4", "Nxd4", "g6"],
    ["c3", "Nf6", "e5", "Nd5"],
]


class TestQuotingEngineLines:
    def test_faithful_quotation_of_an_engine_line_is_allowed(self):
        """The engine searched this line; repeating it is reporting, not
        calculating, so it must survive verification."""
        text = "After 1. Nf3 Nc6 2. d4 cxd4 the centre opens."
        result = verifier.verify(text, SICILIAN, sanctioned_lines=SANCTIONED)
        assert result.ok is True

    def test_quoting_from_the_middle_of_a_line_is_allowed(self):
        text = "Later the engine plays d4 cxd4 Nxd4."
        assert verifier.verify(text, SICILIAN, sanctioned_lines=SANCTIONED).ok is True

    def test_a_line_the_engine_never_searched_is_rejected(self):
        """Plausible-looking but invented - the exact failure mode."""
        text = "After 1. Nf3 e5 2. Bc4 Nf6 White is better."
        result = verifier.verify(text, SICILIAN, sanctioned_lines=SANCTIONED)
        assert result.ok is False

    def test_reordering_a_real_line_is_rejected(self):
        """Every move appears in a sanctioned line, but not in this order."""
        text = "The engine gives 1. Nf3 cxd4 2. Nc6 d4."
        result = verifier.verify(text, SICILIAN, sanctioned_lines=SANCTIONED)
        assert result.ok is False

    def test_mixing_two_separate_lines_is_rejected(self):
        text = "Play 1. Nf3 Nf6 2. e5 Nd5 and White wins."
        assert verifier.verify(text, SICILIAN, sanctioned_lines=SANCTIONED).ok is False

    def test_listing_candidate_moves_is_not_a_line(self):
        """Commas separate a list of options, not a sequence of play."""
        text = "The engine prefers Nf3, Nc3, and Bc4 here."
        assert verifier.find_move_runs(text) == []

    def test_deep_moves_from_a_line_are_claimable(self):
        """d4 is illegal in the current position but appears in a searched
        line, so naming it is a verified claim rather than an invention."""
        assert verifier.find_illegal_moves("Then d4 follows.", SICILIAN,
                                           sanctioned_lines=SANCTIONED) == []

    def test_deep_moves_are_still_rejected_without_sanction(self):
        assert verifier.find_illegal_moves("Then Nxd4 follows.", SICILIAN) == ["Nxd4"]


D6_LINES = [
    ["d5", "Nb8", "h4", "h5", "Bb5+", "Bd7", "Be2", "g6"],
    ["dxc5", "Nf6", "Nc3", "Qa5", "Nd2", "Qxc5", "Nb3", "Qb6"],
]
D6_BOARD = board_after("e4", "c5", "Nf3", "Nc6", "d4", "d6")


class TestTheGameSoFar:
    """Found running the app: after 1. e4 e5, Claude's explanation began
    "After 1. e4 e5" and was rejected twice as an unsearched line."""

    def test_retelling_the_moves_played_is_not_an_invented_line(self):
        board = board_after("e4", "e5", "Nf3", "Nc6")
        result = verifier.verify("After 1. e4 e5 2. Nf3 Nc6 the centre is balanced.", board)
        assert result.ok, result.violations

    def test_naming_a_move_already_played_is_not_an_illegal_move(self):
        board = board_after("e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5")
        assert verifier.find_illegal_moves("After exd5 the queen recaptured.", board) == []

    def test_listing_one_sides_moves_is_not_an_invented_line(self):
        """Round 4: "White has played 1.e4 2.c4 3.Nc3" was rejected as a line."""
        board = board_after("e4", "e5", "c4", "Nc6", "Nc3", "Nf6")
        assert verifier.verify("White has played 1.e4 2.c4 3.Nc3 so far.", board).ok

    def test_one_sides_moves_must_still_be_the_moves_it_played(self):
        board = board_after("e4", "e5", "c4", "Nc6")
        assert not verifier.verify("White has played 1.e4 2.Nf3 so far.", board).ok

    def test_a_line_that_departs_from_the_game_is_still_rejected(self):
        board = board_after("e4", "e5")
        result = verifier.verify("After 1. e4 e5 2. Bc4 Bc5 3. Qh5 it is sharp.", board)
        assert not result.ok


class TestVerify:
    def test_clean_response_passes(self):
        result = verifier.verify("Nf3 is the engine's choice.", SICILIAN)
        assert result.ok is True
        assert result.violations == []

    def test_illegal_move_fails_verification(self):
        result = verifier.verify("Play Bxb5 and win.", SICILIAN)
        assert result.ok is False
        assert any("Bxb5" in v for v in result.violations)

    def test_variation_fails_verification(self):
        result = verifier.verify("After 1. Nf3 d6 2. d4 cxd4 it's equal.", SICILIAN)
        assert result.ok is False


class TestCapturesBeyondTheLine:
    def test_a_recapture_the_engines_line_does_not_play_is_not_accepted(self):
        """Lines now run on to where the engine stops capturing. A capture it
        did not play is one it rejected: round 8's p095 offered Bxd5, which
        loses the knight on d4."""
        board = board_after("e4", "c6")
        line = ["d4", "d5", "e5", "Bf5", "h4", "h5", "Bd3", "Bxd3"]
        text = "White can take back with Qxd3."
        assert verifier.find_illegal_moves(text, board, [line]) == ["Qxd3"]


class TestProseIsLeftToTheSelfCheck:
    def test_claims_about_checks_attacks_and_trades_are_not_judged_here(self):
        """Rounds 4-6: once the model checked its own draft, the patterns that
        read checks, attacks and trades out of prose rejected 20 correct
        answers and caught no wrong one, so verify() no longer runs them."""
        text = "This leads to exchanges of Queens, and Nc3 is check."
        assert verifier.verify(text, D6_BOARD, D6_LINES).ok
