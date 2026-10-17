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
        assert "White is 1 pawn ahead" in facts

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
