"""Asks one model to explain every pinned position, through the coach's own checker.

    python -m evals.collect --model gemma3:12b

Each answer goes through `verified_completion`, the same check-and-retry the app
runs, and every attempt is recorded with the checker's verdict. Resumable: a
position already in the output file is skipped, since a local reasoning model
can take hours over the whole set.
"""

import argparse
import json
import time
from pathlib import Path

import chess

from evals.positions import POSITIONS
from evals.score import DATA
from src.coach import verifier
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


def responses_path(model: str) -> Path:
    return DATA / f"responses-{model.replace(':', '-').replace('/', '-')}.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    llm = LLMClient(model_name=args.model)
    # A fallback would answer with a different model and record it under this one.
    llm.fallback_models = []
    recorder = RecordingLLM(llm)

    out = responses_path(args.model)
    done = {json.loads(line)["id"] for line in out.read_text().splitlines()} if out.exists() else set()
    positions = [json.loads(line) for line in POSITIONS.read_text().splitlines()]

    with out.open("a") as sink:
        for position in positions:
            if position["id"] in done:
                continue
            board = chess.Board()
            for uci in position["moves"]:
                board.push_uci(uci)

            recorder.calls.clear()
            shown = verified_completion(recorder, position["prompt"], board, position["lines"])

            attempts = []
            for text, seconds in recorder.calls:
                result = verifier.verify(text, board, sanctioned_lines=position["lines"])
                attempts.append({
                    "text": text, "ok": result.ok, "violations": result.violations,
                    "seconds": round(seconds, 1),
                })
            if shown is None:
                outcome = "fallback"
            else:
                assert shown == attempts[-1]["text"] and attempts[-1]["ok"]
                outcome = "first" if len(attempts) == 1 else "retry"

            sink.write(json.dumps({
                "id": position["id"], "model": args.model, "outcome": outcome, "attempts": attempts,
            }) + "\n")
            sink.flush()
            print(f"{position['id']}  {outcome:<8} {sum(a['seconds'] for a in attempts):6.1f}s", flush=True)


if __name__ == "__main__":
    main()
