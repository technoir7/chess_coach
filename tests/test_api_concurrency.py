import asyncio
import threading
import time

import httpx

from api import main
from src.models import TruthPacket


class SlowCoach:
    """Explains like the real coach does now: slowly, in blocking calls."""

    def __init__(self):
        self.active = 0
        self.overlapped = False

    def explain_position(self):
        self.active += 1
        self.overlapped |= self.active > 1
        time.sleep(0.5)
        self.active -= 1
        return "explained"

    def build_truth_packet(self):
        return TruthPacket(fen="", engine_eval=0, game_phase="Opening")


class Session:
    def __init__(self, coach):
        self.coach = coach
        self.lock = threading.Lock()


async def _finished(client, url):
    response = await client.get(url)
    return response, time.monotonic()


def test_a_slow_explanation_does_not_freeze_the_server():
    """An explanation takes about 20 seconds of blocking calls; in an async
    endpoint that froze every other request, even loading the page."""
    main.game_manager.games["slow"] = Session(SlowCoach())

    async def run():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            (done, explained_at), (page, page_at) = await asyncio.gather(
                _finished(client, "/api/game/slow/explain"), _finished(client, "/"),
            )
            return done, explained_at, page, page_at

    try:
        done, explained_at, page, page_at = asyncio.run(run())
    finally:
        del main.game_manager.games["slow"]
    assert page.status_code == 200 and done.status_code == 200
    assert page_at < explained_at


def test_requests_for_one_game_still_take_turns():
    coach = SlowCoach()
    main.game_manager.games["one"] = Session(coach)

    async def run():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await asyncio.gather(client.get("/api/game/one/explain"), client.get("/api/game/one/explain"))

    try:
        asyncio.run(run())
    finally:
        del main.game_manager.games["one"]
    assert not coach.overlapped
