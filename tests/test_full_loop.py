import sys
import os
import logging

# Add current directory to path
sys.path.append(os.getcwd())

from src.utils.config import load_config
from src.coach.coach import BerkeleyChaosChessCoach

# Configure logging to see engine output
logging.basicConfig(level=logging.INFO)

def test_advice_loop():
    print("Loading config...")
    config = load_config("system_config.yaml")

    # Initialize Coach
    print("Initializing Coach...")
    coach = BerkeleyChaosChessCoach(config)
    coach.start()

    try:
        # 1. Play a move (e.g., e2e4)
        print("Processing move: e2e4")
        result = coach.process_move("e2e4")
        print(f"Result 1: {result}")

        # 2. Play a blunder (to trigger advice potentially) or just another move
        # Let's play a bad move for black?
        # Black plays f7f6 (weakening)
        print("Processing move: f7f6")
        result = coach.process_move("f7f6")
        print(f"Result 2: {result}")
        
        # 3. White plays d2d4
        print("Processing move: d2d4")
        result = coach.process_move("d2d4")
        print(f"Result 3: {result}")

        # 4. Black plays g7g5 (Fool's mate setup ish?)
        print("Processing move: g7g5")
        result = coach.process_move("g7g5")
        print(f"Result 4: {result}")
        
        # 5. White plays Qh5 checkmate
        print("Processing move: d1h5")
        result = coach.process_move("d1h5")
        print(f"Result 5: {result}")

    except Exception as e:
        print(f"Test Failed: {e}")
        raise
    finally:
        coach.stop()
        print("Coach stopped.")

if __name__ == "__main__":
    test_advice_loop()
