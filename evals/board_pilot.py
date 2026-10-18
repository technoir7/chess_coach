"""Runs the board-tool check over round 6's shown answers, whose labels are known.

    python -m evals.board_pilot

Round 6's reviewers found 7 of 300 shown answers false; they checked each
claim on a board, which the model's own check could not. This gives the
model's check that board (`review.board_prompt`) and runs it over those 7 and a
seeded sample of the correct ones, recording what it changed, how long it took
and how many tokens it used. Only the answers it changes need labelling: an
unchanged answer keeps its round 6 label.
"""

import glob
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor

import chess

from evals.score import round_dir
from src.coach import claude_cli, review

ROUND = 6
CORRECT_SAMPLE = 43
OUT = round_dir(ROUND) / "board-pilot.jsonl"


def shown_answers():
    """Each position's shown answer and whether reviewers found it false."""
    labels = {
        (x["id"], x["attempt"]): bool(x["claims"])
        for x in map(json.loads, (round_dir(ROUND) / "labels.jsonl").read_text().splitlines())
        if x["model"] == "claude-sonnet-claims"
    }
    shown = {}
    for path in sorted(glob.glob(str(round_dir(ROUND) / "responses-claude-sonnet-claims.part*.jsonl"))):
        for response in map(json.loads, open(path)):
            if response["outcome"] == "fallback":
                continue
            attempt = len(response["attempts"]) - 1
            shown[response["id"]] = (response["attempts"][attempt]["text"], labels[(response["id"], attempt)])
    return shown


def main() -> None:
    positions = {p["id"]: p for p in map(json.loads, (round_dir(ROUND) / "positions.jsonl").read_text().splitlines())}
    shown = shown_answers()
    wrong = sorted(i for i, (_, false) in shown.items() if false)
    right = sorted(i for i, (_, false) in shown.items() if not false)
    sample = wrong + sorted(random.Random(2031).sample(right, CORRECT_SAMPLE))
    done = {json.loads(l)["id"] for l in OUT.read_text().splitlines()} if OUT.exists() else set()

    def check(pid):
        position, (text, false) = positions[pid], shown[pid]
        board = chess.Board()
        for uci in position["moves"]:
            board.push_uci(uci)
        pieces = review.sentences(text)
        usage = {}

        def run(*args, **kwargs):
            completed = claude_cli.subprocess.run(*args, **kwargs)
            try:
                reply = json.loads(completed.stdout)
                usage.update(turns=reply.get("num_turns"), usage=reply.get("usage"), cost_usd=reply.get("total_cost_usd"))
            except ValueError:
                pass
            return completed

        started = time.monotonic()
        record = {"id": pid, "was_false": false, "before": text}
        try:
            reply = claude_cli.generate_with_board("claude-sonnet", review.board_prompt(position["prompt"], pieces, board.fen()), run=run)
            record["after"] = review.apply(pieces, reply)
            record["error"] = None
        except (review.ReviewError, claude_cli.ClaudeCLIError) as e:
            record["after"], record["error"] = None, str(e)[:300]
        record.update(changed=record["after"] is not None and record["after"] != text,
                      seconds=round(time.monotonic() - started, 1), **usage)
        return record

    with OUT.open("a") as sink, ThreadPoolExecutor(3) as pool:
        for record in pool.map(check, [p for p in sample if p not in done]):
            sink.write(json.dumps(record) + "\n")
            sink.flush()
            print(f"{record['id']} was_false={record['was_false']} changed={record['changed']} "
                  f"{record['seconds']}s turns={record.get('turns')} error={record['error']}", flush=True)


if __name__ == "__main__":
    main()
