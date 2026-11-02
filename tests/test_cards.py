from datetime import datetime, timezone

import chess
import pytest

from src.games import cards, move_review
from src.games.game import Game
from src.games.move_review import ReviewedGame
from src.games.win_chances import Eval

LEVEL = Eval(cp=0)


def game(moves, color, id="g"):
    return Game(
        id=id, played_at=datetime(2026, 5, 1, tzinfo=timezone.utc), speed="blitz",
        rated=True, color=color, result="loss", termination="resign",
        moves=tuple(moves.split()), clocks=None, initial=None, increment=None,
        opening="", my_rating=1500, opponent_rating=1500, url=f"https://lichess.org/{id}",
    )


def reviewed(g, evals, threats):
    return ReviewedGame(g, move_review.review_game(g, evals, threats), evals, threats)


def evals(count, **at):
    return [at.get(f"p{i}", LEVEL) for i in range(count)]


def mistake(rg):
    return next(r for r in rg.records if r.kind)


SCHOLAR = reviewed(
    game("e4 e5 Bc4 Nc6 Qh5 Nf6 Qxf7#", chess.BLACK),
    evals(8, p5=Eval(cp=0, pv=("g7g6", "h5f3")), p6=Eval(mate=1, pv=("h5f7",)), p7=Eval(mate=1)),
    {5: Eval(mate=1, pv=("h5f7",))},
)
DROPPED_KNIGHT = reviewed(
    game("e4 Nf6 d3 Ne4 dxe4", chess.BLACK),
    evals(6, p3=Eval(cp=30, pv=("d7d5",)), p4=Eval(cp=320, pv=("d3e4", "d7d5"))),
    {3: Eval(cp=40, pv=("b1c3",))},
)
MISSED_KNIGHT = reviewed(
    game("e4 Nf6 d3 Ne4 Nf3 Nf6", chess.WHITE),
    evals(7, p4=Eval(cp=320, pv=("d3e4", "d7d5")), p5=Eval(cp=20, pv=("e4f6",))),
    {4: Eval(cp=330, pv=("e4f6",))},
)


class TestThreatCard:
    def test_asks_what_the_opponent_threatens(self):
        card = cards.build_card(SCHOLAR, mistake(SCHOLAR))
        assert card.kind == move_review.MISSED_THREAT
        assert card.fen == chess.Board("r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3").fen()
        assert card.orientation == chess.BLACK
        assert "threaten" in card.question

    def test_answer_names_the_threat_the_move_played_and_the_better_one(self):
        card = cards.build_card(SCHOLAR, mistake(SCHOLAR))
        text = " ".join(card.answer)
        assert "4. Qxf7#" in text and "mate" in text
        assert "3...Nf6" in text and "3...g6" in text
        assert ("h5f7", cards.THREAT) in card.arrows and ("g7g6", cards.BEST) in card.arrows



class TestAllowedCard:
    def test_shows_the_move_and_asks_what_it_allows(self):
        card = cards.build_card(DROPPED_KNIGHT, mistake(DROPPED_KNIGHT))
        assert card.kind == move_review.ALLOWED_TACTIC
        assert "2...Nxe4" in card.question
        assert card.shown_move == "f6e4"

    def test_answer_gives_their_reply_and_what_it_wins(self):
        card = cards.build_card(DROPPED_KNIGHT, mistake(DROPPED_KNIGHT))
        text = " ".join(card.answer)
        assert "3. dxe4" in text and "2 points" in text and "2...d5" in text



class TestWhatHappened:
    def test_says_when_the_opponent_carried_out_the_threat(self):
        card = cards.build_card(SCHOLAR, mistake(SCHOLAR))
        assert "They played it." in card.answer

    def test_says_when_the_opponent_missed_it(self):
        g = reviewed(
            game("e4 Nf6 d3 Ne4 Nf3", chess.BLACK),
            evals(6, p3=Eval(cp=30, pv=("d7d5",)), p4=Eval(cp=320, pv=("d3e4", "d7d5"))),
            {3: Eval(cp=40, pv=("b1c3",))},
        )
        assert "They missed it and played 3. Nf3." in cards.build_card(g, mistake(g)).answer

    def test_says_how_material_stands_after_the_line(self):
        card = cards.build_card(DROPPED_KNIGHT, mistake(DROPPED_KNIGHT))
        assert "afterwards White is 2 points ahead" in " ".join(card.answer)


class TestShownLine:
    """The card shows a line only as far as the material is won: a blunder
    is its capture, not the trades the engine plays out afterwards."""

    def test_a_blunder_shows_only_the_capture(self):
        card = cards.build_card(DROPPED_KNIGHT, mistake(DROPPED_KNIGHT))
        assert "Their best reply: 3. dxe4, winning" in " ".join(card.answer)

    def test_stops_once_the_material_is_won(self):
        # 1...Bxa1 wins the rook; the engine's line goes on with quiet moves.
        board = chess.Board("rn1qkbnr/pbpppppp/1p6/8/8/6P1/PPPPPP1P/RNBQKBNR b KQkq - 0 3")
        line = cards.shown_line(board, board, ["b7h1", "g1f3", "h1g2"], chess.BLACK)
        assert board.variation_san(line) == "3...Bxh1"

    def test_a_combination_keeps_every_move_it_needs(self):
        # 13. Bxf8 Qxd1 14. Raxd1 Kxf8: the material swings until the last move.
        board = chess.Board("r1bq1rk1/ppp1pp1p/6pB/8/4B3/8/PbP2PPP/R2Q1RK1 w - - 0 13")
        line = cards.shown_line(board, board, ["h6f8", "d8d1", "a1d1", "g8f8", "e4d5"], chess.WHITE)
        assert board.variation_san(line) == "13. Bxf8 Qxd1 14. Raxd1 Kxf8"

    def test_never_stops_just_before_a_recapture(self):
        # 11...e5? 12. dxe6 fxe6 13. Bxe6 Bxe6 14. Rxe6+: the pawn taken on e6
        # is taken back at once; the one White keeps falls at the end.
        start = chess.Board("r3kb1r/ppqnpppp/2pp4/3P1b2/2B2P2/2N2N2/PPPQ2PP/2K1R2R b kq - 0 11")
        board = start.copy()
        board.push_san("e5")
        line = cards.shown_line(start, board, ["d5e6", "f7e6", "c4e6", "f5e6", "e1e6"], chess.WHITE)
        assert board.variation_san(line) == "12. dxe6 fxe6 13. Bxe6 Bxe6 14. Rxe6+"

    def test_a_line_that_wins_nothing_is_kept_whole(self):
        board = chess.Board()
        line = cards.shown_line(board, board, ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"], chess.WHITE)
        assert len(line) == 4


class TestPlayableLine:
    """The app has the player make the line's first move on a board, so each
    card carries where the line starts and its moves."""

    def test_a_threat_starts_from_the_position_with_the_opponent_to_move(self):
        card = cards.build_card(SCHOLAR, mistake(SCHOLAR))
        assert chess.Board(card.line_fen).turn == chess.WHITE
        assert card.line == ("h5f7",)

    def test_an_allowed_tactic_starts_after_the_move_played(self):
        card = cards.build_card(DROPPED_KNIGHT, mistake(DROPPED_KNIGHT))
        board = chess.Board(card.fen)
        board.push_uci("f6e4")
        assert card.line_fen == board.fen() and card.line == ("d3e4",)

    def test_a_tactic_starts_from_the_cards_position(self):
        card = cards.build_card(MISSED_KNIGHT, mistake(MISSED_KNIGHT), second_best=Eval(cp=20))
        assert card.line_fen == card.fen and card.line == ("d3e4",)


class TestTacticCard:
    def test_asks_for_the_move_when_it_stands_out(self):
        card = cards.build_card(MISSED_KNIGHT, mistake(MISSED_KNIGHT), second_best=Eval(cp=20))
        assert card.kind == move_review.MISSED_TACTIC
        assert "best move" in card.question
        assert "3. dxe4" in " ".join(card.answer)

    def test_no_card_when_another_move_is_nearly_as_good(self):
        assert cards.build_card(MISSED_KNIGHT, mistake(MISSED_KNIGHT), second_best=Eval(cp=280)) is None

    def test_needs_the_second_best_move(self):
        with pytest.raises(ValueError):
            cards.build_card(MISSED_KNIGHT, mistake(MISSED_KNIGHT))


class TestTagsAndIds:
    def test_tags(self):
        card = cards.build_card(SCHOLAR, mistake(SCHOLAR))
        assert set(card.tags) >= {"missed_threat", "blitz", "opening", "2026"}

    def test_a_won_position_thrown_away_is_tagged(self):
        g = reviewed(
            game("e4 e5 Bc4 Nc6 Qh5 Nf6 Qxf7#", chess.BLACK),
            evals(8, p5=Eval(cp=-600, pv=("g7g6",)), p6=Eval(mate=1, pv=("h5f7",)), p7=Eval(mate=1)),
            {5: Eval(mate=1, pv=("h5f7",))},
        )
        assert "thrown_win" in cards.build_card(g, mistake(g)).tags

    def test_the_id_is_stable_per_game_and_move(self):
        card = cards.build_card(SCHOLAR, mistake(SCHOLAR))
        assert card.id == "g-5"
        assert card.link == "https://lichess.org/g#6"


def record(ply, kind, drop, low_clock=False):
    return move_review.MoveRecord(
        ply=ply, san="e4", best_san="d4", fen=chess.STARTING_FEN, phase="Middlegame",
        before=60.0, after=60.0 - drop, seconds_left=None, seconds_spent=None,
        low_clock=low_clock, kind=kind,
    )


class TestSelect:
    def test_takes_the_biggest_tactical_mistakes_per_game(self):
        rg = ReviewedGame(game("e4", chess.WHITE), [
            record(0, move_review.MISSED_THREAT, 20),
            record(2, move_review.ALLOWED_TACTIC, 40),
            record(4, move_review.MISSED_TACTIC, 30),
        ], [LEVEL, LEVEL])
        assert [r.ply for _, r in cards.select([rg], per_game=2)] == [2, 4]

    def test_skips_quiet_low_clock_and_small_mistakes(self):
        rg = ReviewedGame(game("e4", chess.WHITE), [
            record(0, move_review.QUIET, 40),
            record(2, move_review.ALLOWED_TACTIC, 40, low_clock=True),
            record(4, move_review.MISSED_THREAT, 11),
        ], [LEVEL, LEVEL])
        assert cards.select([rg], per_game=2, minimum_drop=15) == []


class TestDate:
    def test_a_card_knows_when_its_game_was_played(self):
        assert cards.build_card(SCHOLAR, mistake(SCHOLAR)).played_on == "2026-05-01"
