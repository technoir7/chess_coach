from types import SimpleNamespace

import chess

from src.coach import review
from src.coach.coach import verified_completion


class ScriptedLLM:
    """Answers each call with the next scripted reply and keeps the prompts."""

    def __init__(self, *replies: str):
        self.replies = list(replies)
        self.prompts = []

    def generate_content(self, prompt: str):
        self.prompts.append(prompt)
        return SimpleNamespace(text=self.replies.pop(0))


class TestSelfCheck:
    def test_the_draft_is_sent_back_for_checking_and_the_checked_text_returned(self):
        llm = ScriptedLLM("Draft: the knight is strong.", "The position is balanced.")
        shown = verified_completion(llm, "BRIEF", chess.Board(), [], check=review.rewrite)
        assert shown == "The position is balanced."
        assert "BRIEF" in llm.prompts[1]
        assert "Draft: the knight is strong." in llm.prompts[1]

    def test_the_checked_text_is_what_the_verifier_judges(self):
        """A draft can be wrong as long as the check removes it; what reaches
        the player is the checked text, so that is what gets verified."""
        llm = ScriptedLLM(
            "White should play Qxh7 now.", "White should play Qxh7 now.",
            "Draft again.", "White has a comfortable game.",
        )
        shown = verified_completion(llm, "BRIEF", chess.Board(), [], check=review.rewrite)
        assert shown == "White has a comfortable game."
        assert len(llm.prompts) == 4

    def test_the_edit_check_returns_only_corrections(self):
        llm = ScriptedLLM("White is winning. The knight is strong.", '{"1": "White is slightly better."}')
        shown = verified_completion(llm, "BRIEF", chess.Board(), [], check=review.edit)
        assert shown == "White is slightly better. The knight is strong."

    def test_a_check_that_cannot_be_applied_counts_as_a_failed_attempt(self):
        """Showing the unchecked draft instead would let through exactly what
        the check exists to stop."""
        llm = ScriptedLLM("Draft one.", "not json", "Draft two.", "{}")
        shown = verified_completion(llm, "BRIEF", chess.Board(), [], check=review.edit)
        assert shown == "Draft two."


class TestBoardCheck:
    def test_the_checked_text_gets_a_last_pass_on_the_board(self):
        seen = {}

        def board_check(brief, text, fen):
            seen.update(brief=brief, fen=fen)
            return text.replace("winning", "slightly better")

        llm = ScriptedLLM("White is winning.", "{}")
        shown = verified_completion(llm, "BRIEF", chess.Board(), [], check=review.edit, board_check=board_check)
        assert shown == "White is slightly better."
        assert seen == {"brief": "BRIEF", "fen": chess.Board().fen()}

    def test_a_board_check_that_cannot_be_applied_counts_as_a_failed_attempt(self):
        def board_check(brief, text, fen):
            raise review.ReviewError("not json")

        llm = ScriptedLLM("One.", "{}", "Two.", "{}")
        assert verified_completion(llm, "BRIEF", chess.Board(), [], check=review.edit, board_check=board_check) is None
