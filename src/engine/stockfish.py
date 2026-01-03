import chess.engine
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class AnalysisEngine:
    def __init__(self, engine_path: str = "stockfish", depth: int = 15, multipv: int = 3):
        self.engine_path = engine_path
        self.depth = depth
        self.multipv = multipv
        self.engine: Optional[chess.engine.SimpleEngine] = None

    def start(self):
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            logger.info(f"Started engine: {self.engine_path}")
        except FileNotFoundError:
            logger.error(f"Stockfish engine not found at {self.engine_path}. Please install Stockfish.")
            raise

    def stop(self):
        if self.engine:
            self.engine.quit()

    def analyze(self, board: chess.Board) -> Dict[str, Any]:
        if not self.engine:
            raise RuntimeError("Engine not started")

        info: Union[chess.engine.InfoDict, List[chess.engine.InfoDict]] = self.engine.analyse(
            board, 
            chess.engine.Limit(depth=self.depth), 
            multipv=self.multipv
        )
        
        # Handle multipv return type (list of dicts)
        if isinstance(info, list):
            # Best move is in the first element (pv[0])
            best_info = info[0] if info else {}
            multipv_data = info
        else:
            best_info = info
            multipv_data = [info]

        score = best_info.get("score")
        eval_cp = None
        if score:
            # Get score from White's perspective, using 10000 for mate
            eval_cp = score.white().score(mate_score=10000)

        return {
            "eval_cp": eval_cp,
            "best_move": best_info.get("pv")[0] if best_info.get("pv") else None,
            "depth": best_info.get("depth"),
            "multipv_lines": multipv_data 
        }
