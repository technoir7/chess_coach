import json
import subprocess

import pytest

from src.coach import claude_cli


class FakeRun:
    """Stands in for subprocess.run and remembers how it was called."""

    def __init__(self, stdout="", returncode=0, stderr=""):
        self.result = subprocess.CompletedProcess([], returncode, stdout, stderr)
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


def reply(text, is_error=False):
    return json.dumps({"type": "result", "result": text, "is_error": is_error})


def test_recognises_only_its_own_model_names():
    assert claude_cli.is_claude_model("claude-sonnet")
    assert claude_cli.is_claude_model("claude-opus")
    assert not claude_cli.is_claude_model("gemma3:12b")
    assert not claude_cli.is_claude_model("gemini-2.5-flash")


def test_returns_the_reply_text():
    run = FakeRun(stdout=reply("Nf3 develops the knight."))
    assert claude_cli.generate("claude-sonnet", "Explain.", run=run) == "Nf3 develops the knight."


def test_sends_the_prompt_on_stdin_to_the_chosen_model():
    """Prompts run to thousands of characters with quotes in them; argv is the
    wrong place for that."""
    run = FakeRun(stdout=reply("ok"))
    claude_cli.generate("claude-opus", "the whole prompt", run=run)

    args, kwargs = run.calls[0]
    assert kwargs["input"] == "the whole prompt"
    assert "the whole prompt" not in args
    assert args[args.index("--model") + 1] == "opus"


def test_runs_as_a_plain_completion_with_no_tools_or_customisations():
    """The coach wants text about a position, not an agent that can read files
    or pick up the CLAUDE.md of whatever directory the server started in."""
    run = FakeRun(stdout=reply("ok"))
    claude_cli.generate("claude-sonnet", "p", run=run)

    args, _ = run.calls[0]
    assert args[args.index("--tools") + 1] == ""
    assert "--safe-mode" in args
    assert "--no-session-persistence" in args


def test_a_failed_command_raises_with_its_message():
    run = FakeRun(returncode=1, stderr="Not logged in")
    with pytest.raises(claude_cli.ClaudeCLIError, match="Not logged in"):
        claude_cli.generate("claude-sonnet", "p", run=run)


def test_an_error_reply_raises_rather_than_being_shown_as_advice():
    run = FakeRun(stdout=reply("Usage limit reached", is_error=True))
    with pytest.raises(claude_cli.ClaudeCLIError, match="Usage limit reached"):
        claude_cli.generate("claude-sonnet", "p", run=run)


def test_lists_models_only_when_the_command_is_installed():
    assert claude_cli.available_models(which=lambda name: None) == []
    assert "claude-sonnet" in claude_cli.available_models(which=lambda name: "/bin/claude")


class TestWithTheBoard:
    def test_the_only_tool_is_the_board(self):
        """No shell, no files: the check may describe positions and nothing else."""
        run = FakeRun(stdout=reply("ok"))
        claude_cli.generate_with_board("claude-sonnet", "p", run=run)
        args, kwargs = run.calls[0]
        assert args[args.index("--tools") + 1] == ""
        assert "--strict-mcp-config" in args
        assert args[args.index("--allowedTools") + 1] == "mcp__board__board"
        config = json.loads(args[args.index("--mcp-config") + 1])
        assert config["mcpServers"]["board"]["args"] == ["-m", "src.coach.board_tool"]
        assert kwargs["input"] == "p"

    def test_personal_settings_stay_out(self):
        """--safe-mode would also turn off the board server, so the CLAUDE.md
        and hooks of the user's own settings are kept out another way."""
        run = FakeRun(stdout=reply("ok"))
        claude_cli.generate_with_board("claude-sonnet", "p", run=run)
        args, kwargs = run.calls[0]
        assert args[args.index("--setting-sources") + 1] == "project"
        assert kwargs["cwd"] != claude_cli.REPO

    def test_an_error_reply_raises(self):
        with pytest.raises(claude_cli.ClaudeCLIError):
            claude_cli.generate_with_board("claude-sonnet", "p", run=FakeRun(stdout=reply("boom", is_error=True)))
