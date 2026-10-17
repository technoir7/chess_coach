import random

import pytest

from evals.positions import pick_plies
from evals.score import score


def attempt(ok, text="..."):
    return {"text": text, "ok": ok, "violations": [], "seconds": 1.0}


def response(id, outcome, *attempts, model="m"):
    return {"id": id, "model": model, "outcome": outcome, "attempts": list(attempts)}


def label(id, attempt, *kinds, model="m"):
    return {
        "id": id, "model": model, "attempt": attempt,
        "claims": [{"kind": k, "quote": "", "why": ""} for k in kinds],
    }


class TestPickPlies:
    def test_white_to_move_inside_the_game_one_early_one_late(self):
        for seed in range(50):
            plies = pick_plies(80, random.Random(seed))
            assert len(plies) == 2
            early, late = sorted(plies)
            assert 6 <= early < 30 <= late < 80
            assert early % 2 == 0 and late % 2 == 0

    def test_a_short_game_gives_only_an_early_position(self):
        plies = pick_plies(24, random.Random(1))
        assert len(plies) == 1 and 6 <= plies[0] < 24

    def test_a_game_that_ends_in_the_opening_gives_nothing(self):
        assert pick_plies(6, random.Random(1)) == []


class TestScore:
    def test_counts_wrong_answers_with_and_without_the_checker(self):
        responses = [
            # Wrong, caught, and the retry was right.
            response("a", "retry", attempt(False), attempt(True)),
            # Wrong, missed by the checker, shown.
            response("b", "first", attempt(True)),
            # Right first time.
            response("c", "first", attempt(True)),
            # Right, but rejected twice: a false alarm that cost the player
            # the explanation.
            response("d", "fallback", attempt(False), attempt(False)),
        ]
        labels = [
            label("a", 0, "illegal_move"), label("a", 1),
            label("b", 0, "wrong_piece"),
            label("c", 0),
            label("d", 0), label("d", 1),
        ]
        result = score(responses, labels)["m"]

        assert result["positions"] == 4
        assert result["wrong_unchecked"] == 2  # a and b, as first written
        assert result["wrong_shown"] == 1  # only b reaches the player
        assert result["caught"] == 1  # a
        assert result["fallbacks"] == 1
        assert result["rejections"] == 3
        assert result["false_alarms"] == 2  # both of d's
        assert result["kinds_unchecked"] == {"illegal_move": 1, "wrong_piece": 1}

    def test_separates_what_the_checker_looks_for_from_what_it_cannot(self):
        responses = [
            response("a", "retry", attempt(False), attempt(True)),
            response("b", "first", attempt(True)),
        ]
        labels = [
            label("a", 0, "invented_line"), label("a", 1),
            label("b", 0, "wrong_eval"),
        ]
        result = score(responses, labels)["m"]
        assert result["wrong_in_scope"] == 1
        assert result["caught_in_scope"] == 1

    def test_scores_each_model_separately(self):
        responses = [
            response("a", "first", attempt(True), model="x"),
            response("a", "first", attempt(True), model="y"),
        ]
        labels = [label("a", 0, "other", model="x"), label("a", 0, model="y")]
        result = score(responses, labels)
        assert result["x"]["wrong_unchecked"] == 1
        assert result["y"]["wrong_unchecked"] == 0

    def test_an_unlabelled_attempt_is_an_error_not_a_correct_answer(self):
        responses = [response("a", "retry", attempt(False), attempt(True))]
        with pytest.raises(KeyError):
            score(responses, [label("a", 0, "illegal_move")])

    def test_an_unknown_kind_is_an_error(self):
        responses = [response("a", "first", attempt(True))]
        with pytest.raises(ValueError):
            score(responses, [label("a", 0, "vibes")])


class TestFailedSelfCheck:
    def test_an_attempt_whose_check_failed_has_no_text_to_label(self):
        """The self-check's reply could not be applied, so nothing was shown
        and nothing can be labelled; the retry is the first real answer."""
        failed = {"text": None, "ok": False, "violations": ["self-check failed"], "seconds": 1.0}
        results = score(
            [response("p1", "retry", failed, attempt(True))],
            [label("p1", 1, "other")],
        )["m"]
        assert results["rejections"] == 1
        assert results["false_alarms"] == 0
        assert results["wrong_unchecked"] == 1
        assert results["wrong_shown"] == 1


class TestIdenticalAnswersAreLabelledOnce:
    def test_one_key_per_distinct_answer_to_a_position(self):
        from evals.blind import group
        entries = [
            ({"model": "a", "id": "p1", "attempt": 0}, "same text"),
            ({"model": "b", "id": "p1", "attempt": 0}, "same text"),
            ({"model": "b", "id": "p2", "attempt": 0}, "same text"),
        ]
        groups = group(entries)
        assert sorted(len(v) for v in groups.values()) == [1, 2]
