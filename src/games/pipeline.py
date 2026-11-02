"""From a username to reviewed games: download once, analyse, label mistakes.
Shared by the report and the flashcards."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from src.games import engine_pass, lichess, move_review
from src.games.game import Game
from src.games.move_review import ReviewedGame

OUT = Path("out")


def load_games(username: str, refresh: bool = False, since: Optional[str] = None) -> List[Game]:
    """The player's games with a clock, from out/<user>.ndjson, downloading
    it first if it's missing or `refresh` is set."""
    path = OUT / f"{username.lower()}.ndjson"
    if refresh or not path.exists():
        print(f"Downloading {username}'s games from Lichess...", file=sys.stderr)
        raw = lichess.download_games(username)
        OUT.mkdir(exist_ok=True)
        path.write_text("".join(json.dumps(g) + "\n" for g in raw))
    games = []
    for line in path.read_text().splitlines():
        try:
            game = lichess.parse_game(json.loads(line), username)
        except lichess.UnsupportedGame:
            continue
        if game.speed != "correspondence" and len(game.moves) >= 2:
            games.append(game)
    if since:
        start = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
        games = [g for g in games if g.played_at >= start]
    return games


def review(games: List[Game], depth: int, workers: int) -> List[ReviewedGame]:
    """Runs Stockfish on every position not already in out/evals.jsonl."""
    cache = engine_pass.EvalCache(OUT / "evals.jsonl", depth=depth)
    analysis = engine_pass.analyse_games(games, cache, workers=workers)
    reviewed = []
    for game in games:
        evals, threats = analysis[game.id]
        reviewed.append(ReviewedGame(game, move_review.review_game(game, evals, threats), evals, threats))
    return reviewed
