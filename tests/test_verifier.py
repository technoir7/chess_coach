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


class TestCheckClaims:
    def test_calling_a_real_check_a_check_is_fine(self):
        text = "Bb5+ is check, and Black blocks with Bd7."
        assert verifier.find_false_check_claims(text, D6_BOARD, D6_LINES) == []

    def test_calling_a_quiet_move_a_check_is_caught(self):
        text = "Then Be2 gives check and Black must respond."
        assert verifier.find_false_check_claims(text, D6_BOARD, D6_LINES) == ["Be2"]

    def test_the_check_belongs_to_the_move_nearest_it(self):
        """From the eval: "25. Rf3 Rxe4+, and Black ends up a pawn ahead with
        check" was charged to Rf3, though the check is Rxe4+."""
        text = "After Be2 and Bb5+, with check, Black must block."
        assert verifier.find_false_check_claims(text, D6_BOARD, D6_LINES) == []

    def test_prose_about_checks_without_a_move_is_ignored(self):
        text = "White should look for checks in this position."
        assert verifier.find_false_check_claims(text, D6_BOARD, D6_LINES) == []


class TestExchangeClaims:
    def test_claiming_a_queen_trade_that_never_happens_is_caught(self):
        """Verbatim from a real run: this line was described as leading to
        'exchanges of Queens'. The black queen moves; none is captured."""
        text = "This leads to exchanges of Queens and a simpler position."
        assert verifier.find_false_exchange_claims(text, D6_BOARD, D6_LINES) == ["queen"]

    def test_a_real_pawn_exchange_is_allowed(self):
        text = "White trades pawns with dxc5."
        assert verifier.find_false_exchange_claims(text, D6_BOARD, D6_LINES) == []

    def test_phrasing_with_the_piece_first_is_caught(self):
        text = "The rooks are exchanged shortly after."
        assert verifier.find_false_exchange_claims(text, D6_BOARD, D6_LINES) == ["rook"]


QUIET_LINES = [["c3", "e6", "Bd3", "Nf6"]]


class TestExchangeClaimsInContext:
    """Each sentence is from the eval, where the checker rejected a correct
    answer over it."""

    def test_a_denied_exchange_is_not_a_claimed_one(self):
        for text in (
            "Material stays level and no queens are exchanged.",
            "There are no checks and no queen exchange.",
            "The knight then pressures the queenside pawns, and no pieces are traded.",
        ):
            assert verifier.find_false_exchange_claims(text, D6_BOARD, QUIET_LINES) == [], text

    def test_a_piece_named_later_in_the_sentence_is_not_what_was_traded(self):
        text = "The trade on e5 leaves the d-pawn on e5."
        assert verifier.find_false_exchange_claims(text, D6_BOARD, QUIET_LINES) == []

    def test_an_offered_trade_is_not_a_trade(self):
        text = "White offers a rook trade on d3 before settling the bishop."
        assert verifier.find_false_exchange_claims(text, D6_BOARD, QUIET_LINES) == []

    def test_a_trade_earlier_in_the_game_is_a_true_claim(self):
        board = board_after("d4", "d5", "Bf4", "Bf5", "e3", "e6", "Bd3", "Bxd3", "Qxd3")
        text = "The light-squared bishops were traded on move 4."
        assert verifier.find_false_exchange_claims(text, board, QUIET_LINES) == []

    def test_an_earlier_trade_does_not_excuse_a_claim_about_a_line(self):
        """From the eval: "resulting in a Bishop exchange" described an engine
        line with no bishop capture; that bishops were traded earlier in the
        game makes it no truer."""
        board = board_after("d4", "d5", "Bf4", "Bf5", "e3", "e6", "Bd3", "Bxd3", "Qxd3")
        text = "Nf3 develops, resulting in a bishop exchange."
        assert verifier.find_false_exchange_claims(text, board, QUIET_LINES) == ["bishop"]

    def test_a_plain_claimed_trade_is_still_caught(self):
        text = "A queen trade follows, and the endgame is equal."
        assert verifier.find_false_exchange_claims(text, D6_BOARD, QUIET_LINES) == ["queen"]


class TestAttackClaims:
    def test_a_checking_move_does_not_attack_a_bishop(self):
        """Verbatim from a real run: Bb5+ gives check, so it bears on the king.
        The coach called it an attack on the Black Bishop."""
        text = "White plays Bb5+, attacking the Black Bishop."
        assert verifier.find_false_attack_claims(text, D6_BOARD, D6_LINES) == [
            "Bb5 does not attack a bishop"
        ]

    def test_a_true_attack_claim_passes(self):
        text = "Bb5+ is strong, attacking the king directly."
        assert verifier.find_false_attack_claims(text, D6_BOARD, D6_LINES) == []

    def test_attack_talk_without_a_move_is_ignored(self):
        text = "White should look to attack the king side."
        assert verifier.find_false_attack_claims(text, D6_BOARD, D6_LINES) == []


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
