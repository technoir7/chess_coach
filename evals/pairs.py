"""Puts two arms' answers to each position side by side, for judging which is
more useful.

    python -m evals.pairs make --round 10 --arms A B   # round10/pairs/batch-NN.json
    python -m evals.pairs join --round 10 --arms A B   # round10/pairs/verdicts-NN.jsonl -> pairs.json

Each item holds the position, the facts both answers were written from, and
the two answers shown to the player, in an order drawn at random and recorded
only in `keys.json`, so a judge cannot tell which arm wrote which.
"""

import argparse
import json
import random
import sys
from collections import Counter

from evals.positions import positions_path
from evals.score import round_argument, round_dir

BATCH_SIZE = 50


def _shown(number: int, arm: str):
    """Each position's answer as shown to the player: the last attempt."""
    answers = {}
    for path in sorted(round_dir(number).glob("responses-*.jsonl")):
        for response in map(json.loads, path.read_text().splitlines()):
            if response["model"] == arm:
                answers[response["id"]] = response["attempts"][-1]["text"]
    return answers


def make(number: int, arms) -> None:
    folder = round_dir(number) / "pairs"
    positions = [json.loads(line) for line in positions_path(number).read_text().splitlines()]
    first, second = (_shown(number, arm) for arm in arms)
    rng, items, keys = random.Random(number), [], {}
    for position in positions:
        a, b = first.get(position["id"]), second.get(position["id"])
        if a is None or b is None:
            continue
        order = [(arms[0], a), (arms[1], b)]
        rng.shuffle(order)
        key = f"{position['id']}"
        keys[key] = {"1": order[0][0], "2": order[1][0]}
        items.append({"key": key, "fen": position["fen"], "prompt": position["prompt"],
                      "answer_1": order[0][1], "answer_2": order[1][1]})
    rng.shuffle(items)
    folder.mkdir(exist_ok=True)
    (folder / "keys.json").write_text(json.dumps(keys, indent=1))
    for n, start in enumerate(range(0, len(items), BATCH_SIZE), 1):
        (folder / f"batch-{n:02d}.json").write_text(json.dumps(items[start:start + BATCH_SIZE], indent=1))
    print(f"{len(items)} pairs in {n} batches")


def join(number: int, arms) -> None:
    folder = round_dir(number) / "pairs"
    keys = json.loads((folder / "keys.json").read_text())
    verdicts = {}
    for path in sorted(folder.glob("verdicts-*.jsonl")):
        for entry in map(json.loads, path.read_text().splitlines()):
            if entry["key"] in verdicts:
                sys.exit(f"{entry['key']} judged twice")
            verdicts[entry["key"]] = entry
    missing = set(keys) - set(verdicts)
    if missing:
        sys.exit(f"{len(missing)} pairs unjudged, e.g. {sorted(missing)[:3]}")

    results = {
        key: {**{k: v for k, v in verdicts[key].items() if k != "key"},
              "better": keys[key].get(verdicts[key]["better"], "same")}
        for key in sorted(keys)
    }
    (round_dir(number) / "pairs.json").write_text(json.dumps(results, indent=1))
    print(dict(Counter(r["better"] for r in results.values())))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=["make", "join"])
    round_argument(parser)
    parser.add_argument("--arms", nargs=2, required=True, help="the two models whose answers are compared")
    args = parser.parse_args()
    {"make": make, "join": join}[args.step](args.round, args.arms)
