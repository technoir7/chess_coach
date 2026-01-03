import sys
import os
# Add current directory to path so imports work
sys.path.append(os.getcwd())

from src.utils.config import load_config
from src.coach.coach import BerkeleyChaosChessCoach
from src.ui.cli import ChessCLI

def main():
    try:
        config = load_config("system_config.yaml")
    except Exception as e:
        print(f"Error loading config: {e}")
        return

    # Check for engine path override env var, or default to what's in code/config
    # Ideally should come from config, but for now we rely on the default "stockfish" 
    # or user can edit main.py / config. 
    # Let's assume the user might have set CHESS_ENGINE_PATH
    engine_path = os.getenv("CHESS_ENGINE_PATH", "stockfish")

    coach = BerkeleyChaosChessCoach(config, engine_path=engine_path)
    cli = ChessCLI(coach)
    cli.run()

if __name__ == "__main__":
    main()
