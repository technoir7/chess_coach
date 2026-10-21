import chess

from src.coach import prompts
from src.models import CandidateLine, CoachSpeechRules, TruthPacket


def board_after(*sans: str) -> chess.Board:
    board = chess.Board()
    for san in sans:
        board.push_san(san)
    return board


def packet(**overrides) -> TruthPacket:
    defaults = dict(fen="", engine_eval=0, game_phase="Opening")
    return TruthPacket(**{**defaults, **overrides})


class TestDevelopmentStatus:
    def test_nothing_developed_on_move_one(self):
        """The regression: the model claimed developed bishops and knights
        after 1.e4 c5, when no piece had moved."""
        status = prompts.development_status(board_after("e4", "c5"))
        assert "White has NOT developed any piece" in status
        assert "Black has NOT developed any piece" in status

    def test_names_the_square_a_piece_now_occupies(self):
        """The regression: reporting only the square a piece LEFT ("knight from
        g1") let the model invent the destination - it claimed White had played
        Nc3 in a game where it had played Nf3."""
        status = prompts.development_status(board_after("e4", "c5", "Nf3"))
        assert "Knight on f3" in status
        assert "c3" not in status
        assert "Black has NOT developed any piece" in status

    def test_pawn_moves_are_not_development(self):
        assert "White has NOT developed" in prompts.development_status(board_after("e4"))

    def test_reports_both_sides(self):
        status = prompts.development_status(board_after("e4", "c5", "Nf3", "Nc6"))
        assert "Knight on f3" in status
        assert "Knight on c6" in status


class TestLegalMoves:
    def test_lists_san_not_uci(self):
        moves = prompts.legal_moves_list(board_after("e4", "c5"))
        assert "Nf3" in moves
        assert "g1f3" not in moves

    def test_excludes_illegal_moves(self):
        """Bxb5 was the bait move in manual testing - it must never appear."""
        assert "Bxb5" not in prompts.legal_moves_list(board_after("e4", "c5"))


class TestPieceListing:
    def test_lists_both_colours(self):
        listing = prompts.piece_listing(chess.Board())
        assert "King on e1" in listing
        assert "King on e8" in listing

    def test_omits_captured_pieces(self):
        board = board_after("e4", "d5", "exd5")
        assert "Pawn on d5" in prompts.piece_listing(board)
        # Black's d-pawn is gone; only White's remains on d5
        assert prompts.piece_listing(board).count("Pawn on d5") == 1


class TestRecentMoves:
    def test_empty_history(self):
        assert prompts.recent_moves(chess.Board()) == "Game just started"

    def test_numbers_moves_in_pairs(self):
        assert prompts.recent_moves(board_after("e4", "c5", "Nf3")) == "1. e4 c5\n2. Nf3"

    def test_truncation_is_declared(self):
        """The prompt calls this the complete game, so a silent clip would lie."""
        board = board_after("e4", "c5", "Nf3", "Nc6")
        assert "(earlier moves omitted)" in prompts.recent_moves(board, limit=2)

    def test_short_history_is_not_marked_truncated(self):
        board = board_after("e4", "c5")
        assert "omitted" not in prompts.recent_moves(board)


class TestVibeReading:
    def test_reported_in_words_not_as_a_comparable_number(self):
        """The regression: printing Maia's raw value beside a depth-15
        Stockfish eval let the model report that the two "agreed", when
        1.15 and 2.41 are not even on the same scale."""
        facts = prompts.position_facts(
            chess.Board(), packet(engine_eval=115, vibe_score=2.41), ""
        )
        assert "2.41" not in facts
        assert "club-strength human" in facts
        assert "NOT a second" in facts

    def test_direction_is_preserved(self):
        assert "White" in prompts.vibe_reading(2.41)
        assert "Black" in prompts.vibe_reading(-2.41)

    def test_small_readings_are_balanced(self):
        assert "balanced" in prompts.vibe_reading(0.3)
        assert "balanced" in prompts.vibe_reading(-0.3)

    def test_missing_reading(self):
        assert prompts.vibe_reading(None) == "unavailable"

    def test_the_rules_forbid_treating_it_as_a_second_evaluation(self):
        facts = prompts.position_facts(chess.Board(), packet(), "")
        text = prompts.explain_prompt(facts, "Game just started")
        assert "ONLY evaluation" in text


class TestHistoryReachesEveryPrompt:
    def test_explain_prompt_carries_the_move_history(self):
        """The regression: explain got no history at all, so the model invented
        one - describing a move that had never been played."""
        board = board_after("e4", "c5", "Nf3", "Nc6", "d4", "d6")
        facts = prompts.position_facts(board, packet(), "")
        text = prompts.explain_prompt(facts, prompts.recent_moves(board))
        assert "1. e4 c5" in text
        assert "3. d4 d6" in text

    def test_chat_prompt_carries_the_move_history(self):
        board = board_after("e4", "c5")
        facts = prompts.position_facts(board, packet(), "")
        text = prompts.chat_prompt(facts, prompts.recent_moves(board), "why?")
        assert "1. e4 c5" in text


class TestGamePhase:
    def test_opening(self):
        assert prompts.game_phase(board_after("e4", "c5")) == "Opening"

    def test_a_full_board_is_not_an_endgame_however_long_the_game(self):
        """Round 6: "Endgame phase" at move 22 with every piece still on."""
        board = chess.Board("r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R w KQkq - 0 22")
        assert prompts.game_phase(board) == "Middlegame"

    def test_little_material_left_is_an_endgame_however_early(self):
        board = chess.Board("4k3/pp3ppp/8/8/8/8/PP3PPP/3RK3 w - - 0 12")
        assert prompts.game_phase(board) == "Endgame"

    def test_queens_with_a_minor_piece_each_is_an_endgame(self):
        board = chess.Board("3qk3/pp3ppp/5n2/8/8/5N2/PP3PPP/3QK3 w - - 0 30")
        assert prompts.game_phase(board) == "Endgame"


class TestEngineLines:
    def test_renders_a_line_with_move_numbers(self):
        board = board_after("e4", "c5")
        text = prompts.engine_lines(
            packet(candidate_lines=[
                CandidateLine(move_san="Nf3", eval_cp=35,
                              line_san=["Nf3", "Nc6", "d4", "cxd4"]),
            ]),
            board,
        )
        assert "after Nf3 (35cp, roughly equal)" in text
        assert "2. Nf3 Nc6 3. d4 cxd4" in text

    def test_numbers_correctly_when_black_is_to_move(self):
        board = board_after("e4")
        text = prompts.engine_lines(
            packet(candidate_lines=[
                CandidateLine(move_san="c5", line_san=["c5", "Nf3"]),
            ]),
            board,
        )
        assert "1... c5 2. Nf3" in text

    def test_says_so_when_there_is_nothing_to_quote(self):
        text = prompts.engine_lines(packet(), chess.Board())
        assert "none available" in text
        assert "do not give any move sequence" in text

    def test_lines_reach_the_facts_block(self):
        facts = prompts.position_facts(
            board_after("e4", "c5"),
            packet(candidate_lines=[
                CandidateLine(move_san="Nf3", eval_cp=35, line_san=["Nf3", "Nc6"]),
            ]),
            "",
        )
        assert "ENGINE LINES" in facts
        assert "2. Nf3 Nc6" in facts


class TestPromptAssembly:
    def test_facts_block_carries_the_grounding_data(self):
        facts = prompts.position_facts(
            board_after("e4", "c5"),
            packet(engine_eval=35, vibe_score=0.26, top_moves_san=["Nf3", "Nc3"]),
            opening_info="OPENING: Sicilian Defense (B20)",
        )
        assert "Sicilian Defense" in facts
        assert "NOT developed any piece" in facts
        assert "35 centipawns" in facts
        assert "Nf3, Nc3" in facts

    def test_missing_vibe_does_not_render_as_none(self):
        facts = prompts.position_facts(chess.Board(), packet(), "")
        assert "unavailable" in facts
        assert "None" not in facts

    def test_every_prompt_carries_the_grounding_rules(self):
        """The no-invented-variations rule must reach the model in both paths."""
        facts = prompts.position_facts(
            chess.Board(), packet(), "OPENING: Not in the opening book."
        )
        for text in (prompts.explain_prompt(facts, "Game just started"),
                     prompts.chat_prompt(facts, "Game just started", "why?")):
            assert "QUOTE LINES, NEVER CALCULATE THEM" in text
            assert "LEGAL MOVES CHECK" in text

    def test_advice_prompt_is_grounded_like_the_others(self):
        """In-game advice fires mid-game, where an invented move does the most
        damage - it must carry the same rules as explain and chat."""
        rules = CoachSpeechRules(
            must=["reference_concrete_engine_fact"], must_not=["invent_alternatives"]
        )
        text = prompts.advice_prompt(
            prompts.position_facts(chess.Board(), packet(), ""), rules
        )
        assert "QUOTE LINES, NEVER CALCULATE THEM" in text
        assert "LEGAL MOVES CHECK" in text
        assert "reference_concrete_engine_fact" in text
        assert "invent_alternatives" in text

    def test_chat_prompt_includes_the_question(self):
        facts = prompts.position_facts(chess.Board(), packet(), "")
        assert "What happens after Bxb5?" in prompts.chat_prompt(
            facts, "Game just started", "What happens after Bxb5?"
        )


class TestWhoseMoveItIs:
    def test_states_the_side_to_move_and_the_real_move_number(self):
        """The prompt said "Move 80" in a position at move 41 (it counted
        plies) and never said whose turn it was; answers gave White's moves
        to Black."""
        board = board_after("e4", "c5", "Nf3")
        facts = prompts.position_facts(board, packet(), "")
        assert "Move 2, Black to move" in facts


class TestPieceRelations:
    def test_the_facts_carry_what_each_piece_attacks_and_defends(self):
        board = board_after("e4", "e5", "Nf3", "Nc6")
        facts = prompts.position_facts(board, packet(), "")
        assert "White Knight on f3: attacks Pawn on e5" in facts

    def test_the_rules_point_claims_about_pieces_at_the_relations(self):
        facts = prompts.position_facts(chess.Board(), packet(), "")
        text = prompts.explain_prompt(facts, "Game just started")
        assert "PIECE RELATIONS" in text.split("INSTRUCTIONS:")[1]


class TestPositionsInsideLines:
    def test_each_line_carries_its_move_by_move_and_end_facts(self):
        """Half of round 3's false claims were about positions inside the
        engine lines, which the prompt described only by checks and captures."""
        text = prompts.engine_lines(
            packet(candidate_lines=[
                CandidateLine(move_san="Nf3", eval_cp=35, line_san=["Nf3", "Nc6"]),
            ]),
            board_after("e4", "e5"),
        )
        assert "2. Nf3 (from g1): White Knight on f3 attacks Pawn on e5" in text
        assert "POSITION AT THE END OF THIS LINE" in text

    def test_the_current_position_states_material_and_pawns(self):
        facts = prompts.position_facts(board_after("e4", "d5", "exd5"), packet(), "")
        assert "White is 1 point ahead" in facts

    def test_the_rules_cover_forced_moves_and_counting(self):
        facts = prompts.position_facts(chess.Board(), packet(), "")
        rules = prompts.explain_prompt(facts, "Game just started").split("INSTRUCTIONS:")[1]
        assert "forced" in rules
        assert "MATERIAL AND PAWNS" in rules


class TestEvalInWords:
    def test_every_number_carries_its_band(self):
        """From the eval: -670cp called "a clear edge" - the scale's word for
        101-250 - with the scale twenty lines away."""
        assert prompts.eval_band(-670) == "decisive advantage for Black"
        assert prompts.eval_band(150) == "clear advantage for White"
        assert prompts.eval_band(60) == "slight advantage for White"
        assert prompts.eval_band(-13) == "roughly equal"

    def test_lines_and_the_evaluation_show_the_band(self):
        board = board_after("e4", "c5")
        lines = [CandidateLine(move_san="Nf3", eval_cp=-670, line_san=["Nf3"])]
        facts = prompts.position_facts(board, packet(engine_eval=150, candidate_lines=lines), "")
        assert "after Nf3 (-670cp, decisive advantage for Black)" in facts
        assert "150 centipawns (clear advantage for White)" in facts


class TestUndevelopedPieces:
    def test_names_minor_pieces_still_at_home(self):
        """From the eval: Nbd2 "develops the last minor piece" with the f1
        bishop still at home."""
        status = prompts.development_status(board_after("d4", "d5", "Nf3", "Nf6", "Bf4", "e6"))
        assert "White minor pieces still on their starting squares: Bishop on f1, Knight on b1" in status


class TestHistoryHeader:
    def test_a_clipped_history_is_not_called_the_complete_game(self):
        text = prompts.explain_prompt("facts", "(earlier moves omitted)\n31. Kf1")
        assert "complete game" not in text


def factors(**nets):
    """Even factors, except White ahead by the given amounts (King safety as
    King_safety)."""
    scores = {name: (0.0, 0.0) for name in ("Pawns", "Knights", "Bishops", "Rooks", "Queens",
                                            "Mobility", "King safety", "Passed", "Space")}
    for key, net in nets.items():
        scores[key.replace("_", " ")] = (net, 0.0)
    return scores


class TestTacticalAndPositionalLines:
    def test_a_line_that_wins_material_is_tactical_and_says_who_wins_it(self):
        board = chess.Board("4k3/8/8/3p4/8/8/8/3QK3 w - - 0 1")
        text = prompts.engine_lines(
            packet(candidate_lines=[CandidateLine(move_san="Qxd5", line_san=["Qxd5", "Ke7"])]), board,
        )
        assert "KIND: tactical (White wins 1 point of material)" in text

    def test_a_line_that_loses_material_says_so(self):
        """Round 7: "the line wins material" read as the mover gaining, in
        lines where the mover ended a pawn down."""
        board = chess.Board("4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1")
        text = prompts.engine_lines(
            packet(candidate_lines=[CandidateLine(move_san="Kd2", line_san=["Kd2", "dxe4"])]), board,
        )
        assert "KIND: tactical (Black wins 1 point of material)" in text

    def test_a_quiet_line_is_positional(self):
        text = prompts.engine_lines(
            packet(candidate_lines=[CandidateLine(move_san="Nf3", line_san=["Nf3", "Nc6"])]),
            board_after("e4", "e5"),
        )
        assert "KIND: positional" in text

    def test_a_line_heading_for_mate_beyond_its_moves_is_tactical(self):
        text = prompts.engine_lines(
            packet(candidate_lines=[CandidateLine(move_san="Nf3", line_san=["Nf3", "Nc6"], eval_cp=9985)]),
            board_after("e4", "e5"),
        )
        assert "KIND: tactical (the engine sees a forced mate beyond the moves shown)" in text

    def test_an_even_trade_is_positional(self):
        board = board_after("e4", "d5")
        text = prompts.engine_lines(
            packet(candidate_lines=[CandidateLine(move_san="exd5", line_san=["exd5", "Qxd5"])]), board,
        )
        assert "KIND: positional" in text

    def test_a_line_states_what_it_changes_positionally(self):
        text = prompts.engine_lines(
            packet(factors=factors(), candidate_lines=[
                CandidateLine(move_san="Nf3", line_san=["Nf3", "Nc6"], factors_after=factors(Mobility=0.4)),
            ]),
            board_after("e4", "e5"),
        )
        assert "POSITIONAL CHANGE BY THE END OF THIS LINE: mobility moves 0.40 towards White" in text

    def test_a_line_stopping_mid_exchange_is_compared_once_it_is_played_out(self):
        """A static score with a piece still to be taken back describes a
        position nobody would leave on the board."""
        board = board_after("e4", "d5")
        text = prompts.engine_lines(
            packet(factors=factors(), candidate_lines=[
                CandidateLine(move_san="exd5", line_san=["exd5"], factors_after=factors(Space=0.5)),
            ]),
            board,
        )
        assert (
            "POSITIONAL CHANGE BY THE END OF THIS LINE (with the exchange on d5 played out: Qxd5): "
            "space moves 0.50 towards White"
        ) in text


def quiet(move, eval_cp, after=None, line=None):
    return CandidateLine(move_san=move, line_san=line or [move, "Nc6"], eval_cp=eval_cp,
                         factors_after=factors(**(after or {})))


def why_first(*lines, board=None):
    text = prompts.engine_lines(packet(factors=factors(), candidate_lines=list(lines)),
                                board or board_after("e4", "e5"))
    return [l for l in text.splitlines() if "WHY THE ENGINE RANKS IT FIRST" in l]


class TestWhyTheEngineRanksAQuietMoveFirst:
    """The engine chooses by comparing moves, not by what one move gains on
    the position now. Asked "does it gain anything by the factors?", two in
    three quiet first choices came out unexplained; most had a second move
    within 0.2 pawns, where there is nothing to explain."""

    def test_a_move_within_20cp_is_about_as_good(self):
        [line] = why_first(quiet("Nf3", 30), quiet("Nc3", 15))
        assert "Nc3 is about as good (15cp behind, too little to matter); do not call either better" in line

    def test_a_worse_move_that_loses_material_is_explained_by_that(self):
        [line] = why_first(quiet("Nf3", 30), quiet("Ba6", -250, line=["Ba6", "bxa6"]))
        assert "Ba6 is 280cp worse: its line loses 3 points of material for White" in line

    def test_a_worse_move_is_explained_by_the_factors_where_the_lines_end(self):
        [line] = why_first(quiet("Nf3", 30, after={"Mobility": 0.4}), quiet("Nc3", -20))
        assert "Nc3 is 50cp worse; where the lines end, Nf3's has mobility 0.40 better for White" in line

    def test_small_differences_that_add_up_are_stated_as_such(self):
        [line] = why_first(quiet("Nf3", 30, after={"Mobility": 0.1, "Space": 0.1}), quiet("Nc3", -20))
        assert "where the lines end, Nf3's has small differences in several factors that add up to 0.20 for White" in line

    def test_otherwise_it_says_the_factors_do_not_show_why(self):
        [line] = why_first(quiet("Nf3", 30), quiet("Nc3", -20))
        assert "Nc3 is 50cp worse, for reasons these factors do not show" in line
        assert "do not give a reason of your own" in line

    def test_is_given_once_on_the_first_line_only(self):
        assert len(why_first(quiet("Nf3", 30), quiet("Nc3", 15), quiet("d4", 10))) == 1

    def test_a_small_gap_the_factors_do_not_explain_is_called_small(self):
        [line] = why_first(quiet("Nf3", 30), quiet("Nc3", 0))
        assert "Nc3 is slightly worse (30cp, a small difference), for reasons these factors do not show" in line

    def test_a_first_choice_heading_for_mate_has_none(self):
        """From the eval: a line whose mate came after its eight moves was
        called quiet, and Rd7+ "8982cp worse, for reasons not shown"."""
        assert why_first(quiet("Nf3", 9990), quiet("Nc3", 1000)) == []

    def test_a_tactical_first_choice_has_none(self):
        board = chess.Board("4k3/8/8/3p4/8/8/8/3QK3 w - - 0 1")
        assert why_first(quiet("Qxd5", 900, line=["Qxd5", "Ke7"]), quiet("Kd2", 0, line=["Kd2", "Ke7"]), board=board) == []

    def test_the_rules_say_to_own_up_and_not_to_rank_equal_moves(self):
        rules = prompts.explain_prompt("facts", "Game just started").split("INSTRUCTIONS:")[1]
        assert "WHY THE ENGINE RANKS IT FIRST" in rules
        assert "reasons these factors do not show" in rules
        assert "about as good" in rules

    def test_the_position_part_asks_for_it(self):
        position = prompts.explain_prompt("facts", "Game just started").split("Position:")[1]
        assert "WHY THE ENGINE RANKS IT FIRST" in position


class TestPositionalFactors:
    def test_the_facts_carry_the_factor_table(self):
        facts = prompts.position_facts(chess.Board(), packet(factors=factors(Space=0.3)), "")
        assert "POSITIONAL FACTORS" in facts
        assert "Space (" in facts and "favours White by 0.30" in facts

    def test_the_explanation_keeps_tactics_and_position_apart(self):
        text = prompts.explain_prompt("facts", "Game just started")
        assert "Tactics:" in text and "Position:" in text

    def test_each_line_goes_in_the_part_its_kind_names(self):
        """Round 7: 12 of 100 answers walked through a positional line under
        Tactics."""
        text = prompts.explain_prompt("facts", "Game just started")
        assert "Each engine line goes in the part its KIND names" in text

    def test_the_rules_point_positional_claims_at_the_factors(self):
        facts = prompts.position_facts(chess.Board(), packet(), "")
        rules = prompts.explain_prompt(facts, "Game just started").split("INSTRUCTIONS:")[1]
        assert "POSITIONAL FACTORS" in rules
