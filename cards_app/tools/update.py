"""Bring the phone app up to date: new Lichess games in, cards and
commentary made, app rebuilt.

The app's "Get new games" button runs it through serve_app.py, logging to
cards_app/tools/update.log. By hand:  python3 cards_app/tools/update.py
The Lichess player is read from cards_app/tools/lichess_user (one line, kept
out of git: the deck is one person's).
Exits 0 when done, 2 when done but some new cards lack commentary, 1 on failure.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
REPO = APP.parent
USER_FILE = APP / "tools" / "lichess_user"


def lichess_user() -> str:
    user = USER_FILE.read_text().strip() if USER_FILE.exists() else ""
    if not user:
        raise SystemExit(f"write your Lichess username to {USER_FILE}")
    return user


def run(cmd, cwd: Path) -> bool:
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=cwd).returncode == 0


def main() -> int:
    print(f"--- {datetime.now():%Y-%m-%d %H:%M}", flush=True)
    cards = [str(REPO / "env" / "bin" / "python"), "make_cards.py", lichess_user(), "--refresh"]
    with_commentary = run(cards + ["--commentary"], REPO)
    if not with_commentary:
        # Usually Claude's usage limit. Ship the new cards anyway, without
        # commentary; the next run writes what's missing.
        print("commentary failed; making the cards without it", flush=True)
        if not run(cards, REPO):
            return 1
    if not (run(["pnpm", "deck"], APP) and run(["pnpm", "build"], APP)):
        return 1
    print("done" if with_commentary else "done, some cards without commentary", flush=True)
    return 0 if with_commentary else 2


if __name__ == "__main__":
    sys.exit(main())
