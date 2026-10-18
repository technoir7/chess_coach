"""Asks one model to explain every pinned position, through the coach's own checker.

    python -m evals.collect --round 5 --model claude-sonnet --check edit

Each answer goes through `verified_completion`, the same check-and-retry the app
runs, and every attempt is recorded with the checker's verdict. Resumable: a
position already in the output file is skipped, since a local reasoning model
can take hours over the whole set.

From round 4 the model checks its own draft before the checker sees it
(`src/coach/review.py`). Round 4 also wrote each first draft, as model
`<name>-draft`, to measure the check; from round 5 `--check` picks how it is
done and the answers are recorded as model `<name>-<check>`.
"""

import argparse
import json
import time
from pathlib import Path

import chess

from evals.positions import positions_path
from evals.score import round_argument, round_dir
from src.coach import review, verifier
from src.coach.coach import verified_completion
from src.coach.llm import LLMClient


class RecordingLLM:
    """Passes calls through to a model and keeps what came back."""

    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.model = llm.model
        self.calls = []

    def generate_content(self, prompt: str):
        started = time.monotonic()
        response = self.llm.generate_content(prompt)
        self.calls.append((response.text, time.monotonic() - started))
        return response


def judge(text: str, board: chess.Board, lines) -> dict:
    result = verifier.verify(text, board, sanctioned_lines=lines)
    return {"text": text, "ok": result.ok, "violations": result.violations}


def responses_path(number: int, model: str) -> Path:
    return round_dir(number) / f"responses-{model.replace(':', '-').replace('/', '-')}.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    round_argument(parser)
    parser.add_argument("--model", required=True)
    parser.add_argument("--check", required=True, choices=["rewrite", "edit"])
    parser.add_argument("--part", default="1/1", help="k/n: this run takes every n-th position from the k-th")
    args = parser.parse_args()
    name = f"{args.model}-{args.check}"
    part, parts = map(int, args.part.split("/"))

    llm = LLMClient(model_name=args.model)
    # A fallback would answer with a different model and record it under this one.
    llm.fallback_models = []
    recorder = RecordingLLM(llm)

    # Parts write separate files, so parallel runs never share one; scoring
    # reads every responses file and groups by the model recorded inside.
    suffix = "" if parts == 1 else f".part{part}"
    out = responses_path(args.round, name + suffix)
    done = {json.loads(line)["id"] for line in out.read_text().splitlines()} if out.exists() else set()
    positions = [json.loads(line) for line in positions_path(args.round).read_text().splitlines()]
    positions = positions[part - 1::parts]

    check, checked = getattr(review, args.check), []

    def recording_check(llm, brief, draft):
        """What each attempt's check produced, how long it and its draft took,
        and the check's raw replies; text is None where it could not be applied."""
        before, started = len(recorder.calls), time.monotonic()
        record = {"draft": draft, "draft_seconds": recorder.calls[-1][1]}
        try:
            record["text"] = check(llm, brief, draft)
            record["error"] = None
        except review.ReviewError as e:
            record["text"], record["error"] = None, f"self-check failed: {e}"
            raise
        finally:
            record["seconds"] = round(record["draft_seconds"] + time.monotonic() - started, 1)
            record["replies"] = [text for text, _ in recorder.calls[before:]]
            checked.append(record)
        return record["text"]

    with out.open("a") as sink:
        for position in positions:
            if position["id"] in done:
                continue
            board = chess.Board()
            for uci in position["moves"]:
                board.push_uci(uci)

            recorder.calls.clear()
            checked.clear()
            shown = verified_completion(
                recorder, position["prompt"], board, position["lines"], check=recording_check,
            )

            attempts = [
                {**judge(r["text"], board, position["lines"]), "seconds": r["seconds"], "check_replies": r["replies"]}
                if r["text"] is not None else
                {"text": None, "ok": False, "violations": [r["error"]], "seconds": r["seconds"],
                 "check_replies": r["replies"]}
                for r in checked
            ]
            if shown is None:
                outcome = "fallback"
            else:
                assert shown == attempts[-1]["text"] and attempts[-1]["ok"]
                outcome = "first" if len(attempts) == 1 else "retry"

            sink.write(json.dumps({
                "id": position["id"], "model": name, "outcome": outcome, "attempts": attempts,
            }) + "\n")
            sink.flush()

            print(f"{position['id']}  {outcome:<8} {sum(a['seconds'] for a in attempts):6.1f}s", flush=True)


if __name__ == "__main__":
    main()
