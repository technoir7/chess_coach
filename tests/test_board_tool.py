import json

import chess

from src.coach import board_tool

ITALIAN_FEN = "r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"


class TestReport:
    def test_describes_the_position_after_the_moves(self):
        text = board_tool.report(ITALIAN_FEN, ["O-O", "Nf6"])
        assert "White King on g1" in text
        assert "Black Knight on f6" in text
        assert "White to move" in text

    def test_states_where_every_piece_stands(self):
        """Round 6: "eyes b7, where Black's king sits" with the king on b8."""
        text = board_tool.report("1k6/1p6/8/8/8/5B2/8/6K1 w - - 0 1", [])
        assert "King on b8" in text and "Pawn on b7" in text

    def test_legal_moves_for_both_sides(self):
        text = board_tool.report(ITALIAN_FEN, [])
        assert "Legal moves for White (to move):" in text
        assert "Legal moves Black would have if it were Black's turn:" in text

    def test_a_piece_can_be_taken_off_to_ask_what_if(self):
        """Round 6: a mate said not to depend on the d7 rook, which it did."""
        fen = "6k1/3R1ppp/8/8/8/8/8/6K1 w - - 0 1"
        assert "Rd8#" in board_tool.report(fen, [])
        assert "d7" not in board_tool.report(fen, [], without=["d7"]).split("Legal moves for White")[1].split("\n")[0]

    def test_an_illegal_move_is_reported_not_raised(self):
        text = board_tool.report(ITALIAN_FEN, ["Qxh7"])
        assert "Qxh7 is not legal" in text


class TestServer:
    def call(self, message):
        return board_tool.handle(message)

    def test_lists_one_tool(self):
        reply = self.call({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert [t["name"] for t in reply["result"]["tools"]] == ["board"]

    def test_answers_a_tool_call(self):
        reply = self.call({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "board", "arguments": {"fen": ITALIAN_FEN, "moves": ["O-O"]}},
        })
        assert "White King on g1" in reply["result"]["content"][0]["text"]

    def test_notifications_get_no_reply(self):
        assert self.call({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None

    def test_an_unknown_method_is_an_error(self):
        reply = self.call({"jsonrpc": "2.0", "id": 3, "method": "resources/list"})
        assert reply["error"]["code"] == -32601
