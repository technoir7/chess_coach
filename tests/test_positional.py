import chess

from src.coach import positional

EVEN = {name: (0.0, 0.0) for name in positional.FACTOR_WORDS}


def with_scores(**scores):
    """Factors that are even except as given, keyed as in Stockfish's table
    (King safety as king_safety)."""
    factors = dict(EVEN)
    for key, value in scores.items():
        factors[key.replace("_", " ").capitalize()] = value
    return factors


class TestTheCurrentPosition:
    def test_names_the_side_ahead_in_a_factor(self):
        text = positional.describe(chess.Board(), with_scores(Mobility=(0.5, 0.1)))
        assert "- Mobility (safe squares the pieces can move to): White better by 0.40" in text

    def test_a_small_difference_is_called_even(self):
        text = positional.describe(chess.Board(), with_scores(Space=(0.30, 0.25)))
        assert "- Space (" in text
        assert "): about even" in text.split("- Space (")[1].splitlines()[0]

    def test_every_factor_is_listed(self):
        text = positional.describe(chess.Board(), EVEN)
        assert all(f"- {short.capitalize()} (" in text for short, _ in positional.FACTOR_WORDS.values())

    def test_says_why_there_are_none_when_in_check(self):
        board = chess.Board("4k3/8/8/8/8/8/4q3/4K3 w - - 0 1")
        assert "none: White is in check" in positional.describe(board, None)

    def test_says_when_the_engine_is_not_running(self):
        assert "unavailable" in positional.describe(chess.Board(), None)


class TestWhatALineChanges:
    def test_names_each_factor_that_moves_and_towards_whom(self):
        before = with_scores(King_safety=(0.4, 0.4), Pawns=(0.1, 0.1))
        after = with_scores(King_safety=(0.4, 0.1), Pawns=(0.0, 0.3))
        text = positional.change(chess.Board(), before, after)
        assert "king safety moves 0.30 towards White" in text
        assert "pawn structure moves 0.30 towards Black" in text

    def test_the_biggest_change_comes_first(self):
        before = dict(EVEN)
        after = with_scores(Space=(0.2, 0.0), Mobility=(0.0, 0.6))
        text = positional.change(chess.Board(), before, after)
        assert text.index("mobility") < text.index("space")

    def test_says_so_when_nothing_moves(self):
        text = positional.change(chess.Board(), EVEN, with_scores(Space=(0.05, 0.0)))
        assert "no factor moves by 0.15 or more" in text

    def test_a_line_ending_in_check_has_no_comparison(self):
        end = chess.Board("4k3/8/8/8/8/8/4q3/4K3 w - - 0 1")
        assert "the line ends with White in check" in positional.change(end, EVEN, None)
