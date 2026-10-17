"""Asks one model to explain every pinned position, through the coach's own checker.

    python -m evals.collect --round 2 --model claude-sonnet

Each answer goes through `verified_completion`, the same check-and-retry the app
runs, and every attempt is recorded with the checker's verdict. Resumable: a
position already in the output file is skipped, since a local reasoning model
can take hours over the whole set.

From round 4 the model checks its own draft before the checker sees it. Each
position's first draft is also written, as model `<name>-draft`, so the
drafts can be labelled beside the checked answers: the difference between the
two is what the self-check did.
"""

import argparse
import json
import time
from pathlib import Path

import chess

from evals.positions import positions_path
from evals.score import round_argument, round_dir
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


def judge(text: str, board: chess.Board, lines) -> dict:
    result = verifier.verify(text, board, sanctioned_lines=lines)
    return {"text": text, "ok": result.ok, "violations": result.violations}


def responses_path(number: int, model: str) -> Path:
    return round_dir(number) / f"responses-{model.replace(':', '-').replace('/', '-')}.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    round_argument(parser)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    llm = LLMClient(model_name=args.model)
    # A fallback would answer with a different model and record it under this one.
    llm.fallback_models = []
    recorder = RecordingLLM(llm)

    out = responses_path(args.round, args.model)
    done = {json.loads(line)["id"] for line in out.read_text().splitlines()} if out.exists() else set()
    positions = [json.loads(line) for line in positions_path(args.round).read_text().splitlines()]

    with out.open("a") as sink, responses_path(args.round, f"{args.model}-draft").open("a") as draft_sink:
        for position in positions:
            if position["id"] in done:
                continue
            board = chess.Board()
            for uci in position["moves"]:
                board.push_uci(uci)

            recorder.calls.clear()
            shown = verified_completion(recorder, position["prompt"], board, position["lines"])

            # Calls alternate: a draft, then the model's check of it.
            assert len(recorder.calls) % 2 == 0
            drafts, checked = recorder.calls[0::2], recorder.calls[1::2]
            attempts = [
                {**judge(text, board, position["lines"]), "seconds": round(draft_seconds + seconds, 1)}
                for (_, draft_seconds), (text, seconds) in zip(drafts, checked)
            ]
            if shown is None:
                outcome = "fallback"
            else:
                assert shown == attempts[-1]["text"] and attempts[-1]["ok"]
                outcome = "first" if len(attempts) == 1 else "retry"

            sink.write(json.dumps({
                "id": position["id"], "model": args.model, "outcome": outcome, "attempts": attempts,
            }) + "\n")
            sink.flush()

            text, seconds = drafts[0]
            draft = {**judge(text, board, position["lines"]), "seconds": round(seconds, 1)}
            draft_sink.write(json.dumps({
                "id": position["id"], "model": f"{args.model}-draft",
                "outcome": "first" if draft["ok"] else "fallback", "attempts": [draft],
            }) + "\n")
            draft_sink.flush()
            print(f"{position['id']}  {outcome:<8} {sum(a['seconds'] for a in attempts):6.1f}s", flush=True)


if __name__ == "__main__":
    main()
