import csv
import glob
import os
import logging
from typing import Dict, Optional, Tuple

import chess

logger = logging.getLogger(__name__)

_BOOK_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "openings",
)


class OpeningDB:
    """
    Opening name lookup backed by the local ECO book in data/openings/.

    This used to call the Lichess opening explorer API, but that service has
    been unavailable since early 2026 and every lookup silently degraded to
    "Unknown", which in turn led the coach to describe standard openings as
    unusual. A vendored book keeps lookups correct and offline.

    The book gives names and ECO codes only - the master-game win/draw/loss
    statistics came from the API and have no local equivalent.
    """

    def __init__(self, book_dir: str = _BOOK_DIR):
        self.book_dir = book_dir
        self._book: Dict[str, Tuple[str, str]] = self._load_book()

    def _load_book(self) -> Dict[str, Tuple[str, str]]:
        """Replay each opening's PGN once and index it by resulting position."""
        paths = sorted(glob.glob(os.path.join(self.book_dir, "*.tsv")))
        if not paths:
            raise FileNotFoundError(
                f"No opening book found in {self.book_dir}. "
                "Expected the ECO .tsv files that ship with this repo."
            )

        book: Dict[str, Tuple[str, str]] = {}
        for path in paths:
            with open(path, newline="") as fh:
                for row in csv.DictReader(fh, delimiter="\t"):
                    board = chess.Board()
                    try:
                        for token in row["pgn"].split():
                            # Skip move numbers ("1.", "2.", ...)
                            if token.endswith("."):
                                continue
                            board.push_san(token)
                    except ValueError:
                        logger.warning(f"Skipping unparseable opening: {row.get('name')}")
                        continue
                    book[self._position_key(board.fen())] = (row["eco"], row["name"])

        logger.info(f"Loaded {len(book)} openings from {self.book_dir}")
        return book

    @staticmethod
    def _position_key(fen: str) -> str:
        """Piece placement plus side to move.

        Castling rights and move counters are deliberately excluded: they vary
        between transpositions that reach the same book position.
        """
        fields = fen.split()
        return f"{fields[0]} {fields[1]}"

    def get_opening(self, fen: str) -> Dict:
        """
        Look up the opening for a position.

        Returns {"name", "eco", "moves"} when the position is in the book, or
        an empty dict once play leaves it. "moves" is always empty and is kept
        so callers that rendered master-game statistics still work.
        """
        entry = self._book.get(self._position_key(fen))
        if entry is None:
            return {}

        eco, name = entry
        return {"name": name, "eco": eco, "moves": []}
