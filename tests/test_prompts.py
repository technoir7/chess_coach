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
        assert "after Nf3 (35cp)" in text
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
