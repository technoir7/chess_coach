import json

import chess
import pytest

from src.games import cards, commentary
from tests.test_cards import DROPPED_KNIGHT, MISSED_KNIGHT, SCHOLAR, evals, game, mistake, reviewed
from src.games.win_chances import Eval


def card_and_brief(rg, second_best=None):
    record = mistake(rg)
    card = cards.build_card(rg, record, second_best)
    return card, commentary.brief(card, rg, record)


class TestBrief:
    def test_carries_the_card(self):
        card, b = card_and_brief(SCHOLAR)
        assert card.question in b.text
        assert all(line in b.text for line in card.answer)

    def test_a_threat_card_states_the_threat_from_the_position_with_the_opponent_to_move(self):
        _, b = card_and_brief(SCHOLAR)
        assert "THE THREAT" in b.text and "4. Qxf7#" in b.text
        assert "WHAT THE MOVE PLAYED CHANGED" in b.text
        assert b.threat_fen is not None and chess.Board(b.threat_fen).turn == chess.WHITE

    def test_lines_are_the_only_sequences_it_may_quote(self):
        _, b = card_and_brief(SCHOLAR)
        assert ("Qxf7#",) in b.lines  # the threat
        assert ("Nf6", "Qxf7#") in b.lines  # the move played and their reply
        assert ("g6", "Qf3") in b.lines  # the better move

    def test_each_line_is_played_out_move_by_move(self):
        _, b = card_and_brief(DROPPED_KNIGHT)
        assert "MOVE BY MOVE" in b.text and "POSITION AT THE END OF THIS LINE" in b.text

    def test_the_attacking_line_stops_where_the_cards_does(self):
        """Commentary narrated trades the card had cut ("after 23. a3 Rxd1+
        ... after 24. Qxd1") of a rook simply hung."""
        card, b = card_and_brief(DROPPED_KNIGHT)
        assert "Their best reply: 3. dxe4, winning" in " ".join(card.answer)
        assert ("Nxe4", "dxe4") in b.lines and ("Nxe4", "dxe4", "d5") not in b.lines

    def test_a_tactic_card_has_no_threat_position(self):
        _, b = card_and_brief(MISSED_KNIGHT, Eval(cp=20))
        assert b.threat_fen is None and "THE THREAT" not in b.text


class TestMoveChanges:
    def test_the_moved_piece_left_en_prise(self):
        board = chess.Board()
        for san in "e4 Nf6 d3".split():
            board.push_san(san)
        facts = commentary.move_changes(board, board.parse_san("Nxe4"))
        assert "Black Knight on e4 is attacked by Pawn on d3 and defended by nothing" in facts

    def test_a_piece_it_stopped_defending(self):
        board = chess.Board()
        for san in "e4 e5 Nf3 Nc6 Bc4".split():
            board.push_san(san)
        facts = commentary.move_changes(board, board.parse_san("Nd4"))
        assert "it no longer defends Pawn on e5" in facts
        assert "Black Pawn on e5 was defended by Knight on c6 and is now defended by nothing, attacked by Knight on f3" in facts

    def test_a_piece_it_uncovered(self):
        board = chess.Board("4q2k/4b3/8/8/8/8/8/4R1K1 b - - 0 1")
        facts = commentary.move_changes(board, chess.Move.from_uci("e7f6"))
        assert "Black Queen on e8 is now attacked by Rook on e1; defended by nothing" in facts


class TestEscapes:
    def test_where_an_attacked_piece_can_go_and_what_covers_it(self):
        # After 7...a4 the bishop on b3 is attacked and every square it can reach is covered.
        board = chess.Board("r1bqk1nr/1pp1ppbp/1n1p2p1/p7/3PPB2/1B3N2/PPP2PPP/RN1QK2R b KQkq - 1 7")
        board.push_san("a4")
        [fact] = commentary.escapes(board, chess.A4)
        assert fact.startswith("White Bishop on b3 can go to: ")
        assert "c4 (covered by Knight on b6)" in fact
        assert "xf7+ (covered by King on e8)" in fact

    def test_an_unattacked_square_is_not_called_safe(self):
        """Round 2's "its only safe retreat is g6" took "safe" from the brief;
        the bishop was trapped there two moves later."""
        board = chess.Board()
        board.push_san("e4")
        board.push_san("d5")
        [fact] = commentary.escapes(board, chess.D5)
        assert fact.startswith("White Pawn on e4 can go to: ") and "e5 (not attacked there)" in fact

    def test_the_brief_gives_escapes_after_the_attacking_move(self):
        # 1.e4 e5 2.Bc4 Nf6 3.d3 c6 4.Nc3?: ...d5 hits the bishop and the e4 pawn.
        threat = ("d7d5", "c4b3", "d5e4", "d3e4", "d8d1", "e1d1", "f6e4")
        rg = reviewed(
            game("e4 e5 Bc4 Nf6 d3 c6 Nc3", chess.WHITE),
            evals(8, p6=Eval(cp=30, pv=("g1f3", "d7d5")), p7=Eval(cp=-150, pv=threat)),
            {6: Eval(cp=-160, pv=threat)},
        )
        _, b = card_and_brief(rg)
        assert "White Bishop on c4 can go to:" in b.text


class TestEscapesInCheck:
    def test_no_escape_list_while_in_check(self):
        """A piece can't move while its king is in check; listing it as
        having nowhere to go read as trapped (round 1, card c32)."""
        board = chess.Board("r3k3/8/8/1N6/8/8/8/4K3 w - - 0 1")
        board.push_san("Nc7+")
        assert commentary.escapes(board, chess.C7) == []


class TestEvents:
    def test_discovered_check(self):
        board = chess.Board("4k3/8/8/8/4B3/8/8/4R2K w - - 0 1")
        assert "discovered check by Rook on e1" in commentary.events(board, board.parse_san("Bd5"))

    def test_double_check(self):
        board = chess.Board("4k3/8/8/8/4B3/8/8/4R2K w - - 0 1")
        assert "double check by Bishop on c6 and Rook on e1" in commentary.events(board, board.parse_san("Bc6+"))

    def test_a_new_pin(self):
        board = chess.Board("4k3/4r3/8/8/8/8/8/K6R w - - 0 1")
        assert "Rook on e1 pins Rook on e7 to King on e8" in commentary.events(board, board.parse_san("Re1"))

    def test_a_double_attack(self):
        board = chess.Board("r3k3/8/8/1N6/8/8/8/4K3 w - - 0 1")
        facts = commentary.events(board, board.parse_san("Nc7+"))
        assert "double attack: Knight on c7 attacks King on e8, Rook on a8" in facts

    def test_a_quiet_move_has_none(self):
        assert commentary.events(chess.Board(), chess.Move.from_uci("e2e4")) == []


class TestNetMaterial:
    def test_cancels_even_trades(self):
        """Round 1 read "Qxa5, Rxd1+, Kxd1" as a queen for a rook."""
        board = chess.Board("3rk3/8/8/q7/1Q6/8/8/3RK3 w - - 0 1")
        moves = [chess.Move.from_uci(u) for u in ("b4a5", "d8d1", "e1d1")]
        assert commentary.net_material(board, moves) == (
            "White loses a Rook; Black loses a Queen, a Rook; net, Black gives up a Queen")

    def test_no_captures(self):
        assert commentary.net_material(chess.Board(), [chess.Move.from_uci("e2e4")]) == "nothing is captured"


class TestOverloaded:
    def test_a_lone_defender_of_two_attacked_pieces(self):
        board = chess.Board("7k/8/8/8/8/8/1q1R4/R2Q3K w - - 0 1")
        assert commentary.overloaded(board, chess.WHITE) == [
            "White Queen on d1 is the only defender of Rook on a1, Rook on d2"]

    def test_none_in_the_opening(self):
        assert commentary.overloaded(chess.Board(), chess.WHITE) == []


class TestBetterMove:
    def test_says_the_threat_is_no_longer_possible(self):
        _, b = card_and_brief(SCHOLAR)
        assert "WHAT THE BETTER MOVE DOES" in b.text
        assert "after it, 4. Qxf7# is no longer a legal move" in b.text

    def test_says_what_the_moved_piece_attacks_and_defends(self):
        _, b = card_and_brief(SCHOLAR)
        assert "Black Pawn on g6 attacks Queen on h5" in b.text


class TestOwnership:
    """Rounds 1 and 3 called the opponent's pieces "your" four times."""

    def test_an_opponents_piece_called_yours(self):
        _, b = card_and_brief(SCHOLAR)  # the card is for Black
        assert commentary.wrong_owner("Your bishop on c4 eyes f7.", b) == ["your bishop on c4"]

    def test_your_own_pieces_pass(self):
        _, b = card_and_brief(SCHOLAR)
        assert commentary.wrong_owner("Your Knight on c6 can't help.", b) == []

    def test_a_piece_that_gets_there_in_a_line_passes(self):
        _, b = card_and_brief(SCHOLAR)  # 3...Nf6 is in the played line
        assert commentary.wrong_owner("Your knight on f6 blocks nothing.", b) == []

    def test_write_never_shows_it(self):
        _, b = card_and_brief(SCHOLAR)
        replies = iter(["Your bishop on c4 eyes the f7 pawn.", "{}"] * 2)
        assert commentary.write(b, lambda prompt: next(replies), None) is None


def fake_model(draft, edits="{}", board="{}"):
    replies = iter([draft, edits])
    calls = []

    def generate(prompt):
        calls.append(prompt)
        return next(replies)

    def board_check(prompt):
        calls.append(prompt)
        return board

    return generate, board_check, calls


class TestWrite:
    def test_drafts_checks_and_keeps_both(self):
        _, b = card_and_brief(SCHOLAR)
        generate, board_check, calls = fake_model(
            "The queen and bishop both hit the f7 pawn. Only the king defends it.",
            edits=json.dumps({"2": "Only the king guards it."}),
        )
        result = commentary.write(b, generate, board_check)
        assert result.draft == "The queen and bishop both hit the f7 pawn. Only the king defends it."
        assert result.text == "The queen and bishop both hit the f7 pawn. Only the king guards it."
        assert len(calls) == 3
        assert b.fen in calls[2] and b.threat_fen in calls[2]

    def test_an_invented_move_is_never_shown(self):
        _, b = card_and_brief(SCHOLAR)
        replies = iter(["Play Qxd1 to win.", "{}"] * 2)
        result = commentary.write(b, lambda prompt: next(replies), None)
        assert result is None

    def test_moves_past_the_cards_line_are_never_shown(self):
        _, b = card_and_brief(DROPPED_KNIGHT)
        replies = iter(["After 2...Nxe4 3. dxe4 d5 Black is a knight down.", "{}"] * 2)
        assert commentary.write(b, lambda prompt: next(replies), None) is None

    def test_a_line_nobody_searched_is_never_shown(self):
        _, b = card_and_brief(SCHOLAR)
        replies = iter(["After 3...g6 4. Qf3 Nf6 you are fine.", "{}"] * 2)
        assert commentary.write(b, lambda prompt: next(replies), None) is None
