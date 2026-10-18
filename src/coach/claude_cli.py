"""Claude as the narrator, through the `claude` command and the user's own login.

Calling the CLI rather than the API lets a Claude subscription pay for the
explanations, with no API key to manage. That suits a coach run on your own
machine; a hosted copy would need an API key instead.

Claude Code is an agent, so each call is stripped back to a plain completion:
no tools, no MCP servers, no CLAUDE.md from whatever directory the server
started in, and no saved session.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, List, Optional

# The CLI's own aliases follow the newest model of each size.
MODELS = {
    "claude-sonnet": "sonnet",
    "claude-opus": "opus",
    "claude-haiku": "haiku",
}

SYSTEM_PROMPT = "Reply to the message."

# Generous: a long explanation from the largest model can take most of a minute.
TIMEOUT_SECONDS = 180
# A check that looks positions up on the board takes several turns.
BOARD_TIMEOUT_SECONDS = 420

REPO = Path(__file__).resolve().parents[2]


class ClaudeCLIError(Exception):
    pass


def is_claude_model(name: str) -> bool:
    return name in MODELS


def available_models(which: Callable[[str], Optional[str]] = shutil.which) -> List[str]:
    return list(MODELS) if which("claude") else []


def generate(model: str, prompt: str, run: Callable = subprocess.run) -> str:
    """The model's reply to `prompt`. Raises rather than return an error as text."""
    args = [
        "claude", "-p",
        "--model", MODELS[model],
        "--output-format", "json",
        "--tools", "",
        "--safe-mode",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--system-prompt", SYSTEM_PROMPT,
    ]
    return _result(run(args, input=prompt, capture_output=True, text=True, timeout=TIMEOUT_SECONDS))


def _result(completed) -> str:
    if completed.returncode != 0:
        raise ClaudeCLIError((completed.stderr or completed.stdout).strip())
    reply = json.loads(completed.stdout)
    if reply.get("is_error"):
        raise ClaudeCLIError(reply.get("result", "unknown error"))
    return reply["result"]


def generate_with_board(model: str, prompt: str, run: Callable = subprocess.run) -> str:
    """The model's reply to `prompt`, with the board tool (`board_tool.py`) and
    nothing else to call. Slow: each look at the board is a round trip.

    --safe-mode would turn off the board server too, so the user's own
    settings (their CLAUDE.md, hooks, plugins) are kept out by loading only
    project settings, from a directory that has none.
    """
    server = {"command": sys.executable, "args": ["-m", "src.coach.board_tool"], "env": {"PYTHONPATH": str(REPO)}}
    args = [
        "claude", "-p",
        "--model", MODELS[model],
        "--output-format", "json",
        "--tools", "",
        "--setting-sources", "project",
        "--strict-mcp-config",
        "--mcp-config", json.dumps({"mcpServers": {"board": server}}),
        "--allowedTools", "mcp__board__board",
        "--no-session-persistence",
        "--system-prompt", SYSTEM_PROMPT,
    ]
    return _result(run(
        args, input=prompt, capture_output=True, text=True,
        timeout=BOARD_TIMEOUT_SECONDS, cwd=tempfile.gettempdir(),
    ))
