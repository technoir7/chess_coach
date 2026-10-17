"""Compares two rounds under one standard of labelling.

    python -m evals.cross make --model claude-sonnet   # data/cross-1-2/blind/batch-NN.json
    python -m evals.cross join --model claude-sonnet   # prints both rounds' rates

Each round's labels come from different reviewers, and reviewers differ in how
strict they are: round 2's let pass wording round 1's flagged. So a sample of
first answers from each round is shuffled together and labelled by the same
reviewers, and the rounds are compared only within that sample.
"""

import argparse
import hashlib
import json
import random
import sys

from evals.positions import positions_path
from evals.score import DATA, KINDS
from evals.collect import responses_path

ROUNDS = (1, 2)
SAMPLE = 30
FOLDER = DATA / "cross-1-2"
BLIND = FOLDER / "blind"


def make(model: str) -> None:
    rng = random.Random(2026)
    items, keys = [], {}
    for number in ROUNDS:
        positions = {p["id"]: p for p in map(json.loads, positions_path(number).read_text().splitlines())}
        responses = list(map(json.loads, responses_path(number, model).read_text().splitlines()))
        for response in rng.sample(responses, SAMPLE):
            key = hashlib.sha256(f"{number}|{response['id']}".encode()).hexdigest()[:10]
            keys[key] = {"round": number, "id": response["id"]}
            position = positions[response["id"]]
            items.append({
                "key": key, "fen": position["fen"], "prompt": position["prompt"],
                "answer": response["attempts"][0]["text"],
            })

    rng.shuffle(items)
    BLIND.mkdir(parents=True, exist_ok=True)
    (BLIND / "keys.json").write_text(json.dumps(keys, indent=1))
    half = len(items) // 2
    for n, batch in enumerate((items[:half], items[half:]), 1):
        (BLIND / f"batch-{n:02d}.json").write_text(json.dumps(batch, indent=1))
    print(f"{len(items)} answers in 2 batches")


def join(model: str) -> None:
    keys = json.loads((BLIND / "keys.json").read_text())
    labels = {}
    for path in sorted(BLIND.glob("labels-*.jsonl")):
        for entry in map(json.loads, path.read_text().splitlines()):
            for claim in entry["claims"]:
                if claim["kind"] not in KINDS:
                    sys.exit(f"unknown kind {claim['kind']!r}")
            labels[entry["key"]] = entry["claims"]
    if set(keys) != set(labels):
        sys.exit(f"{len(set(keys) - set(labels))} answers unlabelled")

    results = {}
    for number in ROUNDS:
        mine = [k for k in keys if keys[k]["round"] == number]
        results[f"round{number}"] = {
            "sampled": len(mine),
            "wrong": sum(bool(labels[k]) for k in mine),
        }
    (FOLDER / "labels.jsonl").write_text("".join(
        json.dumps({**keys[k], "model": model, "claims": labels[k]}) + "\n" for k in sorted(keys)
    ))
    (FOLDER / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    for name, r in results.items():
        print(f"{name}: {r['wrong']} of {r['sampled']} first answers wrong")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=["make", "join"])
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    {"make": make, "join": join}[args.step](args.model)
