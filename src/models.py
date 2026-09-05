from typing import List, Optional, Dict, Literal, Union
from pydantic import BaseModel, Field

# --- Philosophy & Axes ---
class Axes(BaseModel):
    coaching_quality: Dict[str, Union[str, bool]] = Field(description="Settings for coaching quality")
    opponent_strength: Dict[str, Union[str, bool]] = Field(description="Settings for opponent strength")

class SystemInfo(BaseModel):
    name: str
    version: Union[str, float]
    philosophy: List[str]

# --- Engines ---
class EngineConfig(BaseModel):
    name: str
    version: Optional[Union[str, int]] = None
    mode: str
    depth_policy: Optional[str] = None
    multipv: Optional[bool] = None
    purpose: Optional[str] = None

class Engines(BaseModel):
    analysis_engine: EngineConfig
    intuition_engine: EngineConfig

# --- LLM ---
class LLMConfig(BaseModel):
    model: str
    role: str
    constraints: List[str]

# --- Opponent ---
class StyleBias(BaseModel):
    enabled: bool
    rules: List[str]

class MoveSelectionPolicy(BaseModel):
    description: str
    parameters: Dict[str, Union[str, StyleBias]]

class OpponentConfig(BaseModel):
    role: str
    engine_source: str
    move_selection_policy: MoveSelectionPolicy

# --- Difficulty ---
class DifficultyLevel(BaseModel):
    eval_window_cp: int

class DifficultyLevels(BaseModel):
    club: DifficultyLevel
    strong_club: DifficultyLevel
    master: DifficultyLevel
    engine: DifficultyLevel

# --- Truth Packet ---
class TruthPacket(BaseModel):
    """Engine-verified facts about a position.

    Everything the coach is allowed to say must be derivable from here - the
    narration layer gets this and nothing else.
    """
    model_config = {"arbitrary_types_allowed": True}

    fen: str
    engine_eval: Optional[float]
    multipv_lines: List[Dict] = []
    null_move_result: Optional[float] = None
    opponent_threats: List[str] = []
    game_phase: str = "middlegame"
    chaos_score: float = 0.0
    vibe_score: Optional[float] = None
    top_moves_san: List[str] = []

class TruthPacketConfig(BaseModel):
    required_fields: List[str]

# --- Logic Gate ---
class LogicGateConfig(BaseModel):
    advice_allowed_if_any: List[str]
    forbid_advice_if: List[str]

# --- Coaching Modes ---
class CoachingMode(BaseModel):
    allows_move_names: bool
    verbosity: Optional[str] = None
    timing: Optional[str] = None

class CoachingModes(BaseModel):
    silent_killer: CoachingMode
    strategic_nudge: CoachingMode
    chaos_maximizer: CoachingMode
    explain_after: CoachingMode

# --- Player Interaction ---
class AnalysisInput(BaseModel):
    enabled: bool
    formats: List[str]

class PlayerInteraction(BaseModel):
    analysis_input: AnalysisInput
    structured_fields: List[str]

# --- Analysis Critique ---
class CritiquePacket(BaseModel):
    required_fields: List[str]

class AnalysisCritique(BaseModel):
    enabled: bool
    critique_packet: CritiquePacket
    critique_modes: List[str]

# --- Coach Speech Rules ---
class CoachSpeechRules(BaseModel):
    must: List[str]
    must_not: List[str]

# --- Key Moment Detector ---
class Irreversibility(BaseModel):
    enabled: bool
    events: List[str]

class PhaseTransition(BaseModel):
    enabled: bool

class KeyMomentDetector(BaseModel):
    triggers: Dict[str, Union[PhaseTransition, Irreversibility, Dict[str, int]]]

# --- Coach Prompts ---
class CoachPrompts(BaseModel):
    type: str
    source: str
    examples: List[str]

# --- Meta Coaching ---
class MetaCoachingOutput(BaseModel):
    frequency: str
    grounded_in_stats: bool

class MetaCoaching(BaseModel):
    enabled: bool
    tracked_patterns: List[str]
    output: MetaCoachingOutput

# --- UI Constraints ---
class UIConstraints(BaseModel):
    default: Dict[str, bool]
    override_requires_explicit_user_action: bool

# --- Anti Cheating ---
class AntiCheating(BaseModel):
    rules: List[str]

# --- Termination Conditions ---
class TerminationConditions(BaseModel):
    coach_silence_if: List[str]

# --- Root Config ---
class SystemConfig(BaseModel):
    system: SystemInfo
    axes: Axes
    engines: Engines
    llm: LLMConfig
    opponent: OpponentConfig
    difficulty_levels: DifficultyLevels
    truth_packet: TruthPacketConfig
    logic_gate: LogicGateConfig
    coaching_modes: CoachingModes
    player_interaction: PlayerInteraction
    analysis_critique: AnalysisCritique
    coach_speech_rules: CoachSpeechRules
    key_moment_detector: KeyMomentDetector
    coach_prompts: CoachPrompts
    meta_coaching: MetaCoaching
    ui_constraints: UIConstraints
    anti_cheating: AntiCheating
    termination_conditions: TerminationConditions
