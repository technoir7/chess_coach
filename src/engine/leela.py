import chess.engine
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class IntuitionEngine:
    """
    Wrapper for Leela Chess Zero (Lc0).
    Focuses on 'positional vibe detection' and human-like evaluation.
    """
    def __init__(self, engine_path: str = "lc0", weights_path: Optional[str] = None):
        self.engine_path = engine_path
        self.weights_path = weights_path
        self.engine: Optional[chess.engine.SimpleEngine] = None

    def start(self):
        try:
            # Lc0 often needs arguments for weights
            args = []
            if self.weights_path:
                args.extend(["--weights", self.weights_path])
            
            self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            # Some UCI engines need options set immediately
            if self.weights_path:
                # Note: This depends on how lc0 is compiled; standard is passing via command line 
                # or setting a UCI option.
                pass
            
            logger.info(f"Started Intuition Engine: {self.engine_path}")
        except FileNotFoundError:
            logger.error(f"Lc0 engine not found at {self.engine_path}.")
            raise

    def stop(self):
        if self.engine:
            self.engine.quit()

    def get_vibe(self, board: chess.Board) -> Dict[str, Any]:
        """
        Analyzes the position to get a 'vibe' (positional score).
        Lc0's WDL (Win/Draw/Loss) is a great 'vibe' indicator.
        """
        if not self.engine:
            return {"vibe_score": 0.0, "top_choice": None}

        # Analyze very quickly (depth 1 or small time limit) for intuition
        info: chess.engine.InfoDict = self.engine.analyse(
            board, 
            chess.engine.Limit(nodes=100) # Fast intuition check
        )

        # Lc0 provides WDL in the info dict if supported
        wdl = info.get("wdl") 
        score = info.get("score")
        
        vibe_score = 0.0
        if score:
             vibe_score = score.white().score(mate_score=10000) / 100.0

        return {
            "vibe_score": vibe_score,
            "top_choice": info.get("pv")[0] if info.get("pv") else None,
            "wdl": str(wdl) if wdl else None
        }
