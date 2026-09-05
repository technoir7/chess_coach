import chess
import pytest

from src.coach.opening_db import OpeningDB


@pytest.fixture(scope="module")
def book():
    return OpeningDB()


def position_after(*sans: str) -> str:
    board = chess.Board()
    for san in sans:
        board.push_san(san)
    return board.fen()


def test_names_the_sicilian():
    """The regression this replaced: a dead API made every opening 'unknown',
    which led the coach to call the Sicilian an unusual opening."""
    entry = OpeningDB().get_opening(position_after("e4", "c5"))
    assert entry["name"] == "Sicilian Defense"
    assert entry["eco"] == "B20"


def test_names_a_transposition(book):
    """Keying on placement + side to move, not move order."""
    via_one = book.get_opening(position_after("d4", "Nf6", "c4"))
    via_other = book.get_opening(position_after("c4", "Nf6", "d4"))
    assert via_one == via_other
    assert via_one["name"]


def test_starting_position_is_not_in_book(book):
    """The ECO book starts at move 1, so the initial position has no entry."""
    assert book.get_opening(chess.Board().fen()) == {}


def test_returns_empty_once_out_of_book(book):
    """A contrived position no opening reaches."""
    board = chess.Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
    assert book.get_opening(board.fen()) == {}


def test_missing_book_fails_loudly(tmp_path):
    with pytest.raises(FileNotFoundError):
        OpeningDB(book_dir=str(tmp_path))
