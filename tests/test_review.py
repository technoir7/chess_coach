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



class TestBoardPrompt:
    def test_gives_the_position_and_the_numbered_answer(self):
        text = review.board_prompt("BRIEF", review.sentences("One. Two."), "8/8/8/8/8/8/8/K6k w - - 0 1")
        assert "8/8/8/8/8/8/8/K6k w - - 0 1" in text
        assert "[1] One." in text and "[2] Two." in text and "BRIEF" in text

    def test_asks_for_lookups_not_memory(self):
        text = review.board_prompt("BRIEF", review.sentences("One."), "fen")
        assert "you must use the board tool" in text and "without" in text


class TestBoard:
    def test_applies_the_corrections_the_board_check_returns(self):
        calls = []

        def generate(model, prompt):
            calls.append((model, prompt))
            return '{"1": "White is slightly better."}'

        text = review.board("claude-sonnet", "BRIEF", "White is winning. The knight is strong.", "FEN", generate=generate)
        assert text == "White is slightly better. The knight is strong."
        assert calls[0][0] == "claude-sonnet" and "FEN" in calls[0][1]


class TestChecklist:
    def test_a_reason_the_factors_do_not_give_counts_as_false(self):
        from src.coach import review
        assert "WHY THE ENGINE RANKS IT FIRST" in review.CHECKLIST
