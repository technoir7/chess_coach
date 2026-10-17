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
    args = parser.parse_args()
    name = f"{args.model}-{args.check}"

    llm = LLMClient(model_name=args.model)
    # A fallback would answer with a different model and record it under this one.
    llm.fallback_models = []
    recorder = RecordingLLM(llm)

    out = responses_path(args.round, name)
    done = {json.loads(line)["id"] for line in out.read_text().splitlines()} if out.exists() else set()
    positions = [json.loads(line) for line in positions_path(args.round).read_text().splitlines()]

    check, checked = getattr(review, args.check), []

    def recording_check(llm, brief, draft):
        """What each attempt's check produced, or None where it could not be applied."""
        try:
            text = check(llm, brief, draft)
        except review.ReviewError as e:
            checked.append((None, f"self-check failed: {e}"))
            raise
        checked.append((text, None))
        return text

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

            # Calls alternate: a draft, then the model's check of it.
            assert len(recorder.calls) == 2 * len(checked)
            seconds = [round(a[1] + b[1], 1) for a, b in zip(recorder.calls[0::2], recorder.calls[1::2])]
            attempts = [
                {**judge(text, board, position["lines"]), "seconds": s}
                if text is not None else
                {"text": None, "ok": False, "violations": [error], "seconds": s}
                for (text, error), s in zip(checked, seconds)
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
            print(f"{position['id']}  {outcome:<8} {sum(seconds):6.1f}s", flush=True)


if __name__ == "__main__":
    main()
