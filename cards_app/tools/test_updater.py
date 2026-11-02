import unittest
from datetime import datetime

from updater import Updater


class FakeRun:
    def __init__(self):
        self.code = None

    def poll(self):
        return self.code


class UpdaterTest(unittest.TestCase):
    def setUp(self):
        self.runs = []

        def start():
            self.runs.append(FakeRun())
            return self.runs[-1]

        self.updater = Updater(start, clock=lambda: datetime(2026, 10, 25, 15, 30), count_cards=lambda: 551)

    def test_idle_until_asked(self):
        self.assertEqual(self.updater.status(), {"state": "idle"})

    def test_a_request_starts_a_run(self):
        self.assertEqual(self.updater.request()["state"], "running")
        self.assertEqual(len(self.runs), 1)

    def test_one_run_at_a_time(self):
        self.updater.request()
        self.updater.request()
        self.assertEqual(len(self.runs), 1)

    def test_reports_how_the_run_ended(self):
        for code, state in ((0, "done"), (2, "partial"), (1, "failed")):
            self.updater.request()
            self.runs[-1].code = code
            self.assertEqual(self.updater.status(), {"state": state, "finished": "2026-10-25T15:30:00", "cards": 551})

    def test_a_new_request_after_a_run_starts_another(self):
        self.updater.request()
        self.runs[-1].code = 0
        self.updater.request()
        self.assertEqual(len(self.runs), 2)


if __name__ == "__main__":
    unittest.main()
