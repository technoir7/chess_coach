"""Review a Lichess player's games: where do they go wrong?

    env/bin/python review_games.py <lichess-username>
    env/bin/python review_games.py <lichess-username> --since 2024-01-01 --refresh

Downloads the games once (out/<user>.ndjson), runs Stockfish over every
position (cached in out/evals.jsonl; the first run on a few hundred games
takes 15-30 minutes), and writes out/<user>-report.md.
"""

import argparse
import os
import sys

from src.games import pipeline, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("username")
    parser.add_argument("--since", help="only games from this date on (YYYY-MM-DD)")
    parser.add_argument("--refresh", action="store_true", help="download the games again")
    parser.add_argument("--depth", type=int, default=16)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    args = parser.parse_args()

    games = pipeline.load_games(args.username, args.refresh, args.since)
    if not games:
        sys.exit("No games to review.")
    reviewed = pipeline.review(games, args.depth, args.workers)

    path = pipeline.OUT / f"{args.username.lower()}-report.md"
    path.write_text(report.render(reviewed, args.username))
    print(f"Wrote {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
