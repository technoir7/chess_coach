from pydantic import BaseModel
from typing import List, Optional, Dict

class MoveRequest(BaseModel):
    move: str  # UCI format, e.g., "e2e4"

class GameState(BaseModel):
    game_id: str
    fen: str
    evaluation: Optional[float]
    move_history: List[str]
    last_move: Optional[str]
    opponent_move: Optional[str]
    game_over: bool
    result: Optional[str]
    position_theme: Optional[str] = None

class ExplainResponse(BaseModel):
    explanation: str
    eval_cp: Optional[float]
    top_moves: List[str]

class CoachAdvice(BaseModel):
    advice: Optional[str]
    triggered: bool

class ChatRequest(BaseModel):
    message: str
    user_analysis: Optional[str] = None

class OpponentSettings(BaseModel):
    difficulty: str
    style: str
    model: Optional[str] = None
