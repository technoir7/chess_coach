import pytest

from src.coach.gate import LogicGate
from src.models import LogicGateConfig, TruthPacket

CONFIG = LogicGateConfig(
    advice_allowed_if_any=[
        "eval_drop_exceeds_threshold",
        "null_move_fails",
        "phase_transition_detected",
        "chaos_score_exceeds_threshold",
    ],
    forbid_advice_if=["no_truth_packet", "eval_stable", "no_concrete_threat"],
)

A_THREAT = ["Rook on e5 is attacked and undefended."]


@pytest.fixture
def gate():
    return LogicGate(CONFIG)


def packet(eval_cp, threats=A_THREAT, phase="Opening", chaos=0.0, null_move=None):
    return TruthPacket(
        fen="",
        engine_eval=eval_cp,
        opponent_threats=threats,
        game_phase=phase,
        chaos_score=chaos,
        null_move_result=null_move,
    )


class TestTheGateOpens:
    def test_blunder_with_a_live_threat_triggers_advice(self, gate):
        """The regression: this returned False for every input, so in-game
        advice never fired once."""
        assert gate.should_advise(packet(-400), packet(30)) is True

    def test_chaos_spike_triggers_advice(self, gate):
        assert gate.should_advise(packet(-50, chaos=0.9), packet(30)) is True

    def test_phase_transition_triggers_advice(self, gate):
        before = packet(30, phase="Opening")
        after = packet(-50, phase="Middlegame")
        assert gate.should_advise(after, before) is True

    def test_failing_null_move_triggers_advice(self, gate):
        assert gate.should_advise(packet(-50, null_move=-300), packet(30)) is True


class TestTheGateStaysShut:
    def test_silent_when_evaluation_is_stable(self, gate):
        assert gate.should_advise(packet(35), packet(30)) is False

    def test_silent_when_there_is_no_concrete_threat(self, gate):
        assert gate.should_advise(packet(-400, threats=[]), packet(30)) is False

    def test_silent_without_a_packet(self, gate):
        assert gate.should_advise(None, packet(30)) is False

    def test_silent_on_the_first_move(self, gate):
        """Nothing to compare against yet."""
        assert gate.should_advise(packet(30), None) is False


class TestMissingEvaluations:
    def test_unknown_current_eval_does_not_crash(self, gate):
        assert gate.should_advise(packet(None), packet(30)) is False

    def test_unknown_previous_eval_does_not_crash(self, gate):
        assert gate.should_advise(packet(-400), packet(None)) is False
