from typing import Optional

from src.models import LogicGateConfig, TruthPacket


class LogicGate:
    """Decides whether an epistemic event justifies speaking at all.

    Silence is the default: a forbid condition vetoes advice outright, and at
    least one allow condition must fire before the coach says anything.
    """

    # A swing smaller than this is noise, not an event.
    EVAL_STABLE_CP = 20
    # A collapse this large means the player gave something up.
    EVAL_DROP_CP = 100
    NULL_MOVE_DROP_CP = 100
    CHAOS_THRESHOLD = 0.7

    def __init__(self, config: LogicGateConfig):
        self.config = config

    def should_advise(
        self,
        truth_packet: Optional[TruthPacket],
        previous_packet: Optional[TruthPacket] = None,
    ) -> bool:
        if not truth_packet:
            return False
        if self._forbidden(truth_packet, previous_packet):
            return False
        return self._allowed(truth_packet, previous_packet)

    @staticmethod
    def _eval_swing(
        packet: TruthPacket, previous: Optional[TruthPacket]
    ) -> Optional[float]:
        """How much ground the player lost since the previous position.

        Engine evaluations are White-relative and the player is White, so a
        positive result means the player's position got worse. Returns None
        when either evaluation is unknown, which is not an event either way.
        """
        if previous is None or packet.engine_eval is None or previous.engine_eval is None:
            return None
        return previous.engine_eval - packet.engine_eval

    def _forbidden(self, packet: TruthPacket, previous: Optional[TruthPacket]) -> bool:
        swing = self._eval_swing(packet, previous)

        for condition in self.config.forbid_advice_if:
            if condition == "eval_stable":
                if swing is not None and abs(swing) < self.EVAL_STABLE_CP:
                    return True
            elif condition == "no_concrete_threat":
                if not packet.opponent_threats:
                    return True
        return False

    def _allowed(self, packet: TruthPacket, previous: Optional[TruthPacket]) -> bool:
        swing = self._eval_swing(packet, previous)

        for condition in self.config.advice_allowed_if_any:
            if condition == "eval_drop_exceeds_threshold":
                if swing is not None and swing > self.EVAL_DROP_CP:
                    return True
            elif condition == "null_move_fails":
                if (
                    packet.null_move_result is not None
                    and packet.engine_eval is not None
                    and (packet.engine_eval - packet.null_move_result) > self.NULL_MOVE_DROP_CP
                ):
                    return True
            elif condition == "phase_transition_detected":
                if previous is not None and previous.game_phase != packet.game_phase:
                    return True
            elif condition == "chaos_score_exceeds_threshold":
                if packet.chaos_score > self.CHAOS_THRESHOLD:
                    return True
        return False
