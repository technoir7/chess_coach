"""Anki flashcards from a Lichess player's own mistakes.

    env/bin/python make_cards.py <lichess-username>
    env/bin/python make_cards.py <lichess-username> --since 2024-01-01 --commentary

Uses the same downloaded games and engine cache as review_games.py, and
writes out/<user>-cards.apkg; double-click it to import into Anki. Importing
a newer deck updates the cards already there. It also writes
out/<user>-cards.json, the deck the phone app (cards_app/) plays.

--commentary adds two or three checked sentences on why, and a lesson, to
the back of each card: about 30 seconds a card with Claude (three at a
time), kept in out/commentary.jsonl so each card is written once.
"""

import argparse
import json
import os
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.coach import claude_cli
from src.games import anki, app_deck, cards, commentary, engine_pass, pipeline
from src.games.move_review import MISSED_TACTIC

COMMENTARY = pipeline.OUT / "commentary.jsonl"
MODEL = "claude-sonnet"


def saved_commentary():
    """Commentary by card id, from the current prompt version only."""
    if not COMMENTARY.exists():
        return {}
    rows = map(json.loads, COMMENTARY.read_text().splitlines())
    return {r["id"]: r["text"] for r in rows if r["version"] == commentary.VERSION}


def write_commentary(chosen, saved, workers=3):
    """Writes commentary for each card not yet saved, saving as it goes so
    a stopped run loses nothing. A card whose commentary fails its checks
    gets none, and is tried again next run."""
    todo = [(card, rg, record) for card, rg, record in chosen if card.id not in saved]

    def run(item):
        card, rg, record = item
        result = commentary.write(commentary.brief(card, rg, record),
                                  lambda p: claude_cli.generate(MODEL, p),
                                  lambda p: claude_cli.generate_with_board(MODEL, p))
        return card.id, result

    failed = 0
    with ThreadPoolExecutor(workers) as executor, COMMENTARY.open("a") as out:
        for done, future in enumerate(as_completed([executor.submit(run, item) for item in todo]), 1):
            card_id, result = future.result()
            if result is None:
                failed += 1
            else:
                saved[card_id] = result.text
                out.write(json.dumps({"id": card_id, "version": commentary.VERSION, "text": result.text}) + "\n")
                out.flush()
            print(f"  commentary {done}/{len(todo)}", file=sys.stderr)
    if failed:
        print(f"{failed} cards' commentary failed its checks; they have none.", file=sys.stderr)
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("username")
    parser.add_argument("--since", help="only games from this date on (YYYY-MM-DD)")
    parser.add_argument("--refresh", action="store_true", help="download the games again")
    parser.add_argument("--per-game", type=int, default=2, help="most cards from one game (default 2)")
    parser.add_argument("--commentary", action="store_true", help="add checked commentary to each card")
    parser.add_argument("--depth", type=int, default=16)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    args = parser.parse_args()

    games = pipeline.load_games(args.username, args.refresh, args.since)
    if not games:
        sys.exit("No games to make cards from.")
    reviewed = pipeline.review(games, args.depth, args.workers)
    chosen = cards.select(reviewed, per_game=args.per_game)

    tactic_fens = [r.fen for _, r in chosen if r.kind == MISSED_TACTIC]
    second_cache = engine_pass.EvalCache(pipeline.OUT / "second_best.jsonl", depth=args.depth)
    seconds = dict(zip(tactic_fens, engine_pass.second_bests(tactic_fens, second_cache, args.workers)))
    built = [(cards.build_card(rg, r, seconds.get(r.fen)), rg, r) for rg, r in chosen]
    built = sorted(((c, rg, r) for c, rg, r in built if c is not None), key=lambda item: item[0].id)
    deck = [card for card, _, _ in built]

    notes = saved_commentary()
    if args.commentary:
        notes = write_commentary(built, notes)

    path = pipeline.OUT / f"{args.username.lower()}-cards.apkg"
    anki.write_deck(deck, notes, path)
    app_deck.write(app_deck.deck(deck, notes), path.with_suffix(".json"))
    kinds = Counter(c.kind for c in deck)
    with_notes = sum(c.id in notes for c in deck)
    print(f"Wrote {path}: {len(deck)} cards ({', '.join(f'{n} {k}' for k, n in kinds.items())}), "
          f"{with_notes} with commentary.", file=sys.stderr)


if __name__ == "__main__":
    main()
