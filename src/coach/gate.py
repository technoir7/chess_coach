from typing import List, Optional
from src.models import LogicGateConfig, TruthPacket

class LogicGate:
    def __init__(self, config: LogicGateConfig):
        self.config = config

    def should_advise(self, truth_packet: Optional[TruthPacket], previous_eval: Optional[float] = None) -> bool:
        """
        Determines if the coach should provide advice based on the truth packet and logic gate configuration.
        """
        if not truth_packet:
            # Forbid advice if no truth packet (implied by "no_truth_packet" rule)
            return False

        # Check forbidding conditions first
        if self._check_forbid_conditions(truth_packet, previous_eval):
            return False

        # Check allowing conditions
        if self._check_allow_conditions(truth_packet, previous_eval):
            return True

        return False

    def _check_forbid_conditions(self, packet: TruthPacket, previous_eval: Optional[float]) -> bool:
        for condition in self.config.forbid_advice_if:
            if condition == "eval_stable":
                # Simplistic check: if eval hasn't changed much (placeholder threshold 20cp)
                if previous_eval is not None and abs(packet.engine_eval - previous_eval) < 20:
                    return True
            elif condition == "no_concrete_threat":
                if not packet.opponent_threats:
                    return True
        return False

    def _check_allow_conditions(self, packet: TruthPacket, previous_eval: Optional[float]) -> bool:
        for condition in self.config.advice_allowed_if_any:
            if condition == "eval_drop_exceeds_threshold":
                # Placeholder threshold: 100cp
                if previous_eval is not None and (previous_eval - packet.engine_eval) > 100:
                    return True
            elif condition == "null_move_fails":
                # If null move result is significantly worse than current eval
                if packet.null_move_result is not None and (packet.engine_eval - packet.null_move_result) > 100:
                    return True
            elif condition == "phase_transition_detected":
                # This would typically be a state change flag passed in or detected
                pass 
            elif condition == "chaos_score_exceeds_threshold":
                if packet.chaos_score > 0.7: # Placeholder threshold
                    return True
        return False
