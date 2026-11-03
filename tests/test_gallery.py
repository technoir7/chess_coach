from evals import gallery


def test_each_answer_is_shown_as_the_player_saw_it_with_its_labelled_false_claims():
    rows = gallery.round_rows(12)
    assert len(rows) == 100
    assert sum(1 for r in rows if r["claims"]) == 1          # results.json: wrong_shown 1
    wrong = next(r for r in rows if r["claims"])
    assert wrong["claims"][0]["quote"] in wrong["text"]
    assert all(r["fen"] and r["best"] for r in rows)
    assert rows[0]["best"] == "O-O" and rows[0]["best_squares"] == ["e1", "g1"]


def test_a_fallback_shows_no_model_text_and_round_one_matches_its_score():
    rows = gallery.round_rows(1)
    assert sum(1 for r in rows if r["claims"]) == 32         # results.json: wrong_shown 32
    fallbacks = [r for r in rows if r["fallback"]]
    assert len(fallbacks) == 7 and all(r["text"] is None and not r["claims"] for r in fallbacks)
