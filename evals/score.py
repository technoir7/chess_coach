"""Turns labelled responses into the numbers the README reports.

    python -m evals.score --round 1

An answer is wrong if its labels list at least one false claim. Every attempt
that was made must be labelled: an unlabelled one is an error here, never
silently counted as correct.
"""

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List

DATA = Path(__file__).parent / "data"


def round_dir(number: int) -> Path:
    """Each round is a fresh set of positions with its own answers and labels:
    a fix prompted by one round's answers is measured on the next round's."""
    return DATA / f"round{number}"


def round_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--round", type=int, required=True, help="which set of positions")


# What the verifier looks for (src/coach/verifier.py) ...
IN_SCOPE = {"illegal_move", "invented_line", "wrong_check", "wrong_capture", "wrong_attack"}
# ... and what it does not.
OUT_OF_SCOPE = {"wrong_piece", "wrong_history", "wrong_eval", "other"}
KINDS = IN_SCOPE | OUT_OF_SCOPE


def score(responses: Iterable[Dict], labels: Iterable[Dict]) -> Dict[str, Dict]:
    claims = {}
    for entry in labels:
        for claim in entry["claims"]:
            if claim["kind"] not in KINDS:
                raise ValueError(f"unknown kind {claim['kind']!r} in {entry}")
        claims[(entry["model"], entry["id"], entry["attempt"])] = {
            c["kind"] for c in entry["claims"]
        }

    results = {}
    for response in responses:
        model = response["model"]
        r = results.setdefault(model, {
            "positions": 0, "wrong_unchecked": 0, "wrong_shown": 0, "caught": 0,
            "wrong_in_scope": 0, "caught_in_scope": 0, "fallbacks": 0,
            "rejections": 0, "false_alarms": 0, "kinds_unchecked": Counter(),
            "seconds": [],
        })
        # An attempt whose self-check could not be applied has no text: nothing
        # was shown, so there is nothing to label.
        kinds = [
            None if a["text"] is None else claims[(model, response["id"], i)]
            for i, a in enumerate(response["attempts"])
        ]
        written = [(a, k) for a, k in zip(response["attempts"], kinds) if k is not None]

        r["positions"] += 1
        r["seconds"] += [a["seconds"] for a in response["attempts"]]

        # Without the checker, the first answer is the one the player would see.
        if written:
            first, first_kinds = written[0]
            first_rejected = not first["ok"]
            r["kinds_unchecked"].update(first_kinds)
            if first_kinds:
                r["wrong_unchecked"] += 1
                r["caught"] += first_rejected
            if first_kinds & IN_SCOPE:
                r["wrong_in_scope"] += 1
                r["caught_in_scope"] += first_rejected

        for attempt, attempt_kinds in zip(response["attempts"], kinds):
            if not attempt["ok"]:
                r["rejections"] += 1
                r["false_alarms"] += attempt_kinds is not None and not attempt_kinds

        # With it, the player sees the last attempt if it passed, otherwise an
        # engine-only summary that cannot be wrong about the position.
        if response["outcome"] == "fallback":
            r["fallbacks"] += 1
        elif kinds[-1]:
            r["wrong_shown"] += 1

    for r in results.values():
        r["kinds_unchecked"] = dict(r["kinds_unchecked"])
        r["median_seconds"] = round(statistics.median(r.pop("seconds")), 1)
    return results


def _read(path: Path) -> List[Dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    round_argument(parser)
    folder = round_dir(parser.parse_args().round)

    responses = [r for path in sorted(folder.glob("responses-*.jsonl")) for r in _read(path)]
    results = score(responses, _read(folder / "labels.jsonl"))
    (folder / "results.json").write_text(json.dumps(results, indent=2) + "\n")

    print(f"{'model':<16}{'wrong, unchecked':>18}{'wrong, shown':>14}{'fallback':>10}{'false alarms':>14}{'median s':>10}")
    for model, r in results.items():
        n = r["positions"]
        print(
            f"{model:<16}{r['wrong_unchecked']:>11} of {n:<4}{r['wrong_shown']:>7} of {n:<4}"
            f"{r['fallbacks']:>10}{r['false_alarms']:>7} of {r['rejections']:<4}{r['median_seconds']:>10}"
        )


if __name__ == "__main__":
    main()
