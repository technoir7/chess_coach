import uuid
import sys
import os
from typing import Dict
import chess

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.coach.coach import ChessCoach
from src.utils.config import load_config

class GameSession:
    def __init__(self, game_id: str, coach: ChessCoach):
        self.game_id = game_id
        self.coach = coach
        self.move_history: list = []
        self.events: list = [] # Store full event log (move + annotation)
        self.resigned = False
        self.draw_agreed = False
        
    def get_state_dict(self) -> dict:
        """Convert game state to dictionary for API response"""
        is_over = self.coach.board.is_game_over() or self.resigned or self.draw_agreed
        
        result = None
        if self.coach.board.is_game_over():
            result = self.coach.board.result()
        elif self.resigned:
            # If user resigns, they lose. 
            # If player is white, black wins (0-1). If player is black, white wins (1-0).
            import chess
            result = "0-1" if self.coach.player_color == chess.WHITE else "1-0"
        elif self.draw_agreed:
            result = "1/2-1/2"

        return {
            "game_id": self.game_id,
            "fen": self.coach.board.fen(),
            "evaluation": self.coach.previous_eval,
            "move_history": self.move_history,
            "last_move": self.move_history[-1] if self.move_history else None,
            "game_over": is_over,
            "result": result,
            "difficulty": self.coach.opponent.difficulty,
            "style": self.coach.opponent.style,
            "position_theme": self.coach.get_position_theme()
        }
    
    def update_settings(self, difficulty: str, style: str, model: str = None):
        """Update opponent settings and optionally the LLM model"""
        self.coach.opponent.set_difficulty(difficulty)
        self.coach.opponent.set_style(style)
        
        # Update LLM model if provided
        if model:
            from src.coach.llm import LLMClient
            self.coach.llm = LLMClient(model_name=model)
            self.coach.reset_cooldown()

class GameManager:
    def __init__(self, config_path: str = "system_config.yaml"):
        self.games: Dict[str, GameSession] = {}
        self.config = load_config(config_path)
        
    def create_game(self) -> str:
        """Create a new game session"""
        game_id = str(uuid.uuid4())
        coach = ChessCoach(self.config)
        coach.start()
        
        session = GameSession(game_id, coach)
        self.games[game_id] = session
        
        return game_id
    
    def get_game(self, game_id: str) -> GameSession:
        """Get a game session by ID"""
        if game_id not in self.games:
            raise ValueError(f"Game {game_id} not found")
        return self.games[game_id]
    
    def cleanup_game(self, game_id: str):
        """Clean up a game session"""
        if game_id in self.games:
            self.games[game_id].coach.stop()
            del self.games[game_id]
