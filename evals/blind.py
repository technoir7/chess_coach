"""Hides which model wrote each answer and what the checker said, for labelling.

    python -m evals.blind make --round 2   # round2/blind/batch-NN.json, answers shuffled
    python -m evals.blind join --round 2   # round2/blind/labels-NN.jsonl -> round2/labels.jsonl

A labeller who knew the checker had rejected an answer, or that a stronger
model wrote it, would look harder or less hard. Each batch item carries only an
opaque key, the position and the answer text.
"""

import argparse
import hashlib
import json
import random
import sys

from evals.positions import positions_path
from evals.score import round_argument, round_dir

BATCH_SIZE = 30


def _key(model: str, id: str, attempt: int) -> str:
    return hashlib.sha256(f"{model}|{id}|{attempt}".encode()).hexdigest()[:10]


def make(number: int) -> None:
    folder, blind = round_dir(number), round_dir(number) / "blind"
    positions = {
        p["id"]: p for p in map(json.loads, positions_path(number).read_text().splitlines())
    }
    items, keys = [], {}
    for path in sorted(folder.glob("responses-*.jsonl")):
        for response in map(json.loads, path.read_text().splitlines()):
            position = positions[response["id"]]
            for attempt, entry in enumerate(response["attempts"]):
                if entry["text"] is None:
                    continue
                key = _key(response["model"], response["id"], attempt)
                keys[key] = {"model": response["model"], "id": response["id"], "attempt": attempt}
                items.append({
                    "key": key, "fen": position["fen"], "prompt": position["prompt"],
                    "answer": entry["text"],
                })

    random.Random(2026).shuffle(items)
    blind.mkdir(exist_ok=True)
    (blind / "keys.json").write_text(json.dumps(keys, indent=1))
    for n, start in enumerate(range(0, len(items), BATCH_SIZE), 1):
        (blind / f"batch-{n:02d}.json").write_text(json.dumps(items[start:start + BATCH_SIZE], indent=1))
    print(f"{len(items)} answers in {n} batches")


def join(number: int) -> None:
    folder, blind = round_dir(number), round_dir(number) / "blind"
    keys = json.loads((blind / "keys.json").read_text())
    labels = {}
    for path in sorted(blind.glob("labels-*.jsonl")):
        for entry in map(json.loads, path.read_text().splitlines()):
            if entry["key"] in labels:
                sys.exit(f"{entry['key']} labelled twice")
            labels[entry["key"]] = entry["claims"]

    missing = set(keys) - set(labels)
    if missing:
        sys.exit(f"{len(missing)} answers unlabelled, e.g. {sorted(missing)[:3]}")

    (folder / "labels.jsonl").write_text("".join(
        json.dumps({**keys[key], "claims": labels[key]}) + "\n" for key in sorted(keys)
    ))
    print(f"{len(keys)} labels joined")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=["make", "join"])
    round_argument(parser)
    args = parser.parse_args()
    {"make": make, "join": join}[args.step](args.round)
