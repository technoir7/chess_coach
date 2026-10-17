from types import SimpleNamespace

import chess

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
        shown = verified_completion(llm, "BRIEF", chess.Board(), [])
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
        shown = verified_completion(llm, "BRIEF", chess.Board(), [])
        assert shown == "White has a comfortable game."
        assert len(llm.prompts) == 4
