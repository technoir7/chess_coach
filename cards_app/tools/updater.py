"""Runs update.py when the phone asks, one run at a time, and remembers how
the last run ended so the phone can ask again after the screen locks."""

import json
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
# update.py's exit codes.
ENDINGS = {0: "done", 2: "partial"}


def start_update():
    """update.py in the background, appending to update.log."""
    log = (HERE / "update.log").open("a")
    return subprocess.Popen([sys.executable, str(HERE / "update.py")], cwd=HERE.parent.parent,
                            stdout=log, stderr=subprocess.STDOUT)


def count_cards() -> int:
    """Cards in the deck the app is built from; the phone compares it with its own."""
    return len(json.loads((HERE.parent / "src" / "generated" / "deck.json").read_text())["cards"])


class Updater:
    def __init__(self, start=start_update, clock=datetime.now, count_cards=count_cards):
        self._start = start
        self._clock = clock
        self._count_cards = count_cards
        self._lock = threading.Lock()
        self._run = None
        self._last = {"state": "idle"}

    def request(self) -> dict:
        with self._lock:
            if self._current() is None:
                self._run = self._start()
            return self._current()

    def status(self) -> dict:
        with self._lock:
            return self._current() or self._last

    def _current(self):
        """The running run's status, or None once it has ended (recording how)."""
        if self._run is None:
            return None
        code = self._run.poll()
        if code is None:
            return {"state": "running"}
        self._last = {"state": ENDINGS.get(code, "failed"), "finished": self._clock().isoformat(timespec="seconds"),
                      "cards": self._count_cards()}
        self._run = None
        return None
