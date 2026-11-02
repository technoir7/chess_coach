"""Card commentary rounds: draw cards, write commentary, hide which is which, score.

    python -m evals.cards.run collect --round 1 --user <lichess-username>
    python -m evals.cards.run blind --round 1
    (reviewers write evals/data/cards-round1/blind/labels-NN.jsonl)
    python -m evals.cards.run score --round 1
    python -m evals.cards.run second --round 1   # checked commentary only, for new reviewers
    python -m evals.cards.run score-second --round 1

Cards come from the player's deck, as make_cards.py builds it, drawn at
random from those no earlier round (or development) used. What links a card
to its game stays in out/, which git ignores; the committed data names cards
c01, c02, ...
"""

import argparse
import hashlib
import json
import random
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.coach import claude_cli
from src.games import cards, commentary, engine_pass, pipeline
from src.games.move_review import MISSED_TACTIC

DATA = Path(__file__).resolve().parents[1] / "data"
PRIVATE = pipeline.OUT / "cards-eval"
CARDS_PER_ROUND = 40
BATCH_SIZE = 20
MODEL = "claude-sonnet"

# Games whose cards were read while commentary was being built.
DEVELOPMENT_GAMES = {"lmD4lvCW", "wB89Ijm3", "JC1VeeVb", "PtXMzLxu", "2hMipToP", "ck2Rq0eG",
                     "Efpj1TtD", "K6f4rUyu", "n6Y9n8Bu"}


def round_dir(number: int) -> Path:
    return DATA / f"cards-round{number}"


def _deck(username: str):
    reviewed = pipeline.review(pipeline.load_games(username), depth=16, workers=8)
    chosen = cards.select(reviewed)
    seconds = engine_pass.EvalCache(pipeline.OUT / "second_best.jsonl", depth=16)
    built = []
    for rg, record in chosen:
        card = cards.build_card(rg, record, seconds.get(record.fen) if record.kind == MISSED_TACTIC else None)
        if card is not None:
            built.append((card, rg, record))
    return built


def _used() -> set:
    used = set()
    for path in PRIVATE.glob("round*-ids.json"):
        used |= set(json.loads(path.read_text()).values())
    return used


def collect(number: int, username: str, workers: int = 3) -> None:
    folder = round_dir(number)
    if folder.exists():
        sys.exit(f"{folder} exists: a round's cards are drawn once")
    used = _used()
    pool = [(c, rg, r) for c, rg, r in _deck(username)
            if c.id not in used and c.id.split("-")[0] not in DEVELOPMENT_GAMES]
    drawn = random.Random(number).sample(pool, CARDS_PER_ROUND)
    names = {f"c{n:02d}": card.id for n, (card, _, _) in enumerate(drawn, 1)}
    PRIVATE.mkdir(parents=True, exist_ok=True)
    (PRIVATE / f"round{number}-ids.json").write_text(json.dumps(names, indent=1))

    def run(item):
        name, (card, rg, record) = item
        b = commentary.brief(card, rg, record)
        start = time.time()
        result = commentary.write(b, lambda p: claude_cli.generate(MODEL, p),
                                  lambda p: claude_cli.generate_with_board(MODEL, p))
        return {
            "id": name, "kind": card.kind, "fen": card.fen, "threat_fen": b.threat_fen,
            "player": "White" if card.orientation else "Black", "question": card.question,
            "answer": list(card.answer), "brief": b.text,
            "draft": result.draft if result else None, "text": result.text if result else None,
            "seconds": round(time.time() - start, 1),
        }

    folder.mkdir(parents=True)
    with ThreadPoolExecutor(workers) as executor:
        rows = list(executor.map(run, zip(names, drawn)))
    (folder / "responses.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"{len(rows)} cards, {sum(r['text'] is None for r in rows)} without commentary")


def _key(card_id: str, text: str) -> str:
    return hashlib.sha256(f"{card_id}|{text}".encode()).hexdigest()[:10]


def blind(number: int) -> None:
    folder = round_dir(number)
    rows = [json.loads(l) for l in (folder / "responses.jsonl").read_text().splitlines()]
    keys, items = {}, {}
    for row in rows:
        for arm in ("draft", "text"):
            if row[arm] is None:
                continue
            key = _key(row["id"], row[arm])
            keys.setdefault(key, []).append({"id": row["id"], "arm": arm})
            items[key] = {
                "key": key, "player": row["player"], "fen": row["fen"], "threat_fen": row["threat_fen"],
                "question": row["question"], "answer": row["answer"], "brief": row["brief"],
                "commentary": row[arm],
            }
    shuffled = list(items.values())
    random.Random(2026 + number).shuffle(shuffled)
    out = folder / "blind"
    out.mkdir(exist_ok=True)
    (out / "keys.json").write_text(json.dumps(keys, indent=1))
    for n, start in enumerate(range(0, len(shuffled), BATCH_SIZE), 1):
        (out / f"batch-{n:02d}.json").write_text(json.dumps(shuffled[start:start + BATCH_SIZE], indent=1))
    print(f"{len(shuffled)} commentaries in {n} batches")


def second(number: int) -> None:
    """The checked commentary alone, reshuffled, for a second set of
    reviewers: how much the count depends on who labels it."""
    folder = round_dir(number)
    rows = [json.loads(l) for l in (folder / "responses.jsonl").read_text().splitlines()]
    items = [{"key": _key(r["id"], r["text"]), "player": r["player"], "fen": r["fen"],
              "threat_fen": r["threat_fen"], "question": r["question"], "answer": r["answer"],
              "brief": r["brief"], "commentary": r["text"]} for r in rows if r["text"] is not None]
    random.Random(4052 + number).shuffle(items)
    out = folder / "second"
    out.mkdir(exist_ok=True)
    half = (len(items) + 1) // 2
    for n, batch in enumerate((items[:half], items[half:]), 1):
        (out / f"batch-{n:02d}.json").write_text(json.dumps(batch, indent=1))
    print(f"{len(items)} commentaries in 2 batches")


def score_second(number: int) -> None:
    folder = round_dir(number)
    labels = [json.loads(l) for p in sorted((folder / "second").glob("labels-*.jsonl"))
              for l in p.read_text().splitlines()]
    results = {"commentaries": len(labels), "wrong": sum(bool(l["claims"]) for l in labels),
               "teaches": dict(Counter(l["teaches"] for l in labels)),
               "lesson_fits": sum(l["lesson_fits"] == "yes" for l in labels)}
    (folder / "results-second.json").write_text(json.dumps(results, indent=1))
    print(json.dumps(results, indent=1))


def score(number: int) -> None:
    folder = round_dir(number)
    keys = json.loads((folder / "blind" / "keys.json").read_text())
    labels = {}
    for path in sorted((folder / "blind").glob("labels-*.jsonl")):
        for entry in map(json.loads, path.read_text().splitlines()):
            if entry["key"] in labels:
                sys.exit(f"{entry['key']} labelled twice")
            labels[entry["key"]] = entry
    missing = set(keys) - set(labels)
    if missing:
        sys.exit(f"{len(missing)} commentaries unlabelled, e.g. {sorted(missing)[:3]}")

    rows = [json.loads(l) for l in (folder / "responses.jsonl").read_text().splitlines()]
    results = {}
    for arm in ("draft", "text"):
        shown = [labels[_key(r["id"], r[arm])] for r in rows if r[arm] is not None]
        results[arm] = {
            "commentaries": len(shown),
            "wrong": sum(bool(l["claims"]) for l in shown),
            "teaches": dict(Counter(l["teaches"] for l in shown)),
            "lesson_fits": sum(l["lesson_fits"] == "yes" for l in shown),
        }
    results["without_commentary"] = sum(r["text"] is None for r in rows)
    results["median_seconds"] = statistics.median(r["seconds"] for r in rows)
    results["changed_by_checks"] = sum(r["text"] is not None and r["draft"] != r["text"] for r in rows)
    (folder / "results.json").write_text(json.dumps(results, indent=1))
    print(json.dumps(results, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=["collect", "blind", "score", "second", "score-second"])
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--user")
    args = parser.parse_args()
    if args.step == "collect":
        if not args.user:
            sys.exit("collect needs --user")
        collect(args.round, args.user)
    else:
        {"blind": blind, "score": score, "second": second, "score-second": score_second}[args.step](args.round)


if __name__ == "__main__":
    main()
