import chess

from src.coach import prompts
from src.models import CoachSpeechRules, TruthPacket


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

    def test_reports_a_developed_knight(self):
        status = prompts.development_status(board_after("e4", "c5", "Nf3"))
        assert "White has moved: knight from g1" in status
        assert "Black has NOT developed any piece" in status

    def test_pawn_moves_are_not_development(self):
        assert "White has NOT developed" in prompts.development_status(board_after("e4"))


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


class TestGamePhase:
    def test_opening(self):
        assert prompts.game_phase(board_after("e4", "c5")) == "Opening"


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

    def test_missing_vibe_renders_as_na_not_none(self):
        facts = prompts.position_facts(chess.Board(), packet(), "")
        assert "Leela Vibe Score: N/A" in facts

    def test_every_prompt_carries_the_grounding_rules(self):
        """The no-invented-variations rule must reach the model in both paths."""
        facts = prompts.position_facts(
            chess.Board(), packet(), "OPENING: Not in the opening book."
        )
        for text in (prompts.explain_prompt(facts),
                     prompts.chat_prompt(facts, "Game just started", "why?")):
            assert "NO CALCULATING VARIATIONS" in text
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
        assert "NO CALCULATING VARIATIONS" in text
        assert "LEGAL MOVES CHECK" in text
        assert "reference_concrete_engine_fact" in text
        assert "invent_alternatives" in text

    def test_chat_prompt_includes_the_question(self):
        facts = prompts.position_facts(chess.Board(), packet(), "")
        assert "What happens after Bxb5?" in prompts.chat_prompt(
            facts, "Game just started", "What happens after Bxb5?"
        )
