"""Download a player's games from Lichess and turn them into `Game`s."""

import json
from datetime import datetime, timezone
from typing import Dict, List

import chess
import requests

from src.games.game import Game

API = "https://lichess.org/api/games/user/{username}"

# Lichess answers 404 to requests that don't say which program is asking.
USER_AGENT = "chess-coach game review (https://github.com/technoir7/chess_coach)"


class UnsupportedGame(Exception):
    """A game this review can't use: another variant, or a set-up start."""


def download_games(username: str, session=requests) -> List[Dict]:
    """Every game the player has on Lichess, newest first, as Lichess's JSON.
    One request, streamed; a few hundred games take a few seconds."""
    response = session.get(
        API.format(username=username),
        headers={"User-Agent": USER_AGENT, "Accept": "application/x-ndjson"},
        params={"clocks": "true", "opening": "true", "evals": "false"},
        stream=True,
        timeout=60,
    )
    response.raise_for_status()
    return [json.loads(line) for line in response.iter_lines(decode_unicode=True) if line]


def parse_game(raw: Dict, username: str) -> Game:
    if raw.get("variant") != "standard":
        raise UnsupportedGame(f"{raw.get('id')}: variant {raw.get('variant')}")

    players = raw["players"]
    me = username.lower()
    sides = {
        color: name for color, name in (("white", chess.WHITE), ("black", chess.BLACK))
        if players[color].get("user", {}).get("id") == me
    }
    if not sides:
        raise ValueError(f"{username} did not play in game {raw.get('id')}")
    side, color = next(iter(sides.items()))
    other = "black" if side == "white" else "white"

    winner = raw.get("winner")
    result = "draw" if winner is None else ("win" if winner == side else "loss")

    clock = raw.get("clock")
    clocks = raw.get("clocks")
    return Game(
        id=raw["id"],
        played_at=datetime.fromtimestamp(raw["createdAt"] / 1000, tz=timezone.utc),
        speed=raw["speed"],
        rated=raw["rated"],
        color=color,
        result=result,
        termination=raw["status"],
        moves=tuple(raw.get("moves", "").split()),
        clocks=tuple(c / 100 for c in clocks) if clocks and clock else None,
        initial=clock["initial"] if clock else None,
        increment=clock["increment"] if clock else None,
        opening=raw.get("opening", {}).get("name", "Unknown"),
        my_rating=players[side].get("rating"),
        opponent_rating=players[other].get("rating"),
        url=f"https://lichess.org/{raw['id']}" + ("/black" if color == chess.BLACK else ""),
    )
