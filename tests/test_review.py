import pytest

from src.coach import review


class TestSentences:
    def test_pieces_join_back_to_the_text(self):
        text = "White is better. After 15. e4 Bf5 16... Nd7 Black holds.\n- The rook is active!"
        assert "".join(review.sentences(text)) == text

    def test_move_numbers_do_not_end_a_sentence(self):
        pieces = review.sentences("The line 15. e4 d5 16. exd5 wins. Black is lost.")
        assert [p.strip() for p in pieces] == ["The line 15. e4 d5 16. exd5 wins.", "Black is lost."]

    def test_each_line_is_its_own_piece(self):
        pieces = review.sentences("**Evaluation:** equal\n- Nf3 develops")
        assert [p.strip() for p in pieces] == ["**Evaluation:** equal", "- Nf3 develops"]


class TestApplyingCorrections:
    def test_replaces_and_deletes_numbered_sentences(self):
        pieces = review.sentences("One. Two. Three.")
        assert review.apply(pieces, '{"2": "Second.", "3": ""}') == "One. Second. "

    def test_no_corrections_leaves_the_draft(self):
        pieces = review.sentences("One. Two.")
        assert review.apply(pieces, "{}") == "One. Two."

    def test_tolerates_a_code_fence(self):
        pieces = review.sentences("One. Two.")
        assert review.apply(pieces, '```json\n{"1": "Uno."}\n```') == "Uno. Two."

    def test_a_number_outside_the_draft_is_an_error(self):
        with pytest.raises(review.ReviewError):
            review.apply(review.sentences("One."), '{"4": "Four."}')

    def test_a_reply_that_is_not_json_is_an_error(self):
        with pytest.raises(review.ReviewError):
            review.apply(review.sentences("One."), "Looks fine to me.")


class TestPrompts:
    def test_rewrite_prompt_carries_the_brief_and_the_draft(self):
        text = review.rewrite_prompt("BRIEF WITH FACTS", "A DRAFT ANSWER")
        assert "BRIEF WITH FACTS" in text and "A DRAFT ANSWER" in text
        assert "corrected explanation only" in text

    def test_edit_prompt_numbers_the_sentences(self):
        text = review.edit_prompt("BRIEF", review.sentences("One. Two."))
        assert "[1] One." in text and "[2] Two." in text


import json
from types import SimpleNamespace

import chess


class ScriptedLLM:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    def generate_content(self, prompt):
        self.prompts.append(prompt)
        return SimpleNamespace(text=self.replies.pop(0))


ITALIAN = chess.Board("r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
LINES = [["O-O", "Nf6"]]
CONNECTED = {"sentence": 2, "at": {"line": "O-O", "after": "4. O-O"}, "kind": "connected_rooks",
             "args": {"side": "White"}, "holds": True}


def reply(corrections=None, claims=()):
    return json.dumps({"corrections": corrections or {}, "claims": list(claims)})


class TestClaimsCheck:
    def test_true_claims_pass_with_one_call(self):
        llm = ScriptedLLM(reply({"1": "White is better."}, [{**CONNECTED, "holds": False}]))
        text = review.claims(llm, "BRIEF", "White is winning. Castling keeps the rooks apart.", ITALIAN, LINES)
        assert text == "White is better. Castling keeps the rooks apart."
        assert len(llm.prompts) == 1

    def test_a_false_claim_is_sent_back_with_the_truth(self):
        llm = ScriptedLLM(
            reply({}, [CONNECTED]),
            reply({"2": "Castling gets the king safe."}, []),
        )
        text = review.claims(llm, "BRIEF", "White is better. Castling connects the rooks.", ITALIAN, LINES)
        assert text == "White is better. Castling gets the king safe."
        assert "Bishop on c1" in llm.prompts[1]
        assert "[2] Castling connects the rooks." in llm.prompts[1]

    def test_a_sentence_still_false_after_its_fix_is_deleted(self):
        llm = ScriptedLLM(
            reply({}, [CONNECTED]),
            reply({"2": "Castling links the rooks."}, [CONNECTED]),
        )
        text = review.claims(llm, "BRIEF", "White is better. Castling connects the rooks.", ITALIAN, LINES)
        assert text == "White is better. "

    def test_a_reply_without_a_claims_list_is_an_error(self):
        with pytest.raises(review.ReviewError):
            review.claims(ScriptedLLM('{"corrections": {}}'), "BRIEF", "One.", ITALIAN, LINES)

    def test_the_prompt_lists_the_kinds_the_board_can_settle(self):
        text = review.claims_prompt("BRIEF", review.sentences("One."))
        assert "connected_rooks" in text and "can_move" in text and "[1] One." in text


class TestFirstPass:
    def test_the_text_before_the_board_checks_its_claims(self):
        """The eval labels this beside the final text, to measure what the
        board's check of the claims adds over the model's own check."""
        first = reply({"1": "White is better."}, [CONNECTED])
        assert review.first_pass("White is winning. Castling connects the rooks.", first) == \
            "White is better. Castling connects the rooks."
