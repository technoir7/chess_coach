import chess
import random
from typing import List, Dict, Any
from src.engine.stockfish import AnalysisEngine

class OpponentPolicy:
    """
    Implements the 'sample from near-optimal moves' policy.
    Selects moves within an eval window based on difficulty level.
    """
    def __init__(self, engine: AnalysisEngine, difficulty: str = "club", style: str = "neutral"):
        self.engine = engine
        self.difficulty = difficulty
        self.style = style
        
        # Difficulty level eval windows (in centipawns)
        self.eval_windows = {
            "club": 200,
            "strong_club": 100,
            "master": 50,
            "engine": 0
        }
        
        self.eval_window_cp = self.eval_windows.get(difficulty, 200)

    def set_difficulty(self, difficulty: str):
        self.difficulty = difficulty
        self.eval_window_cp = self.eval_windows.get(difficulty, 200)

    def set_style(self, style: str):
        self.style = style
    
    def select_move(self, board: chess.Board) -> chess.Move:
        """
        Selects a move from the position using the near-optimal sampling policy.
        """
        # Get multipv analysis
        analysis = self.engine.analyze(board)
        multipv_lines = analysis.get("multipv_lines", [])
        
        if not multipv_lines:
            # Fallback: random legal move
            return random.choice(list(board.legal_moves))
        
        # Extract best eval
        best_info = multipv_lines[0]
        best_score = best_info.get("score")
        
        if not best_score:
            # Fallback
            return best_info.get("pv")[0] if best_info.get("pv") else random.choice(list(board.legal_moves))
        
        best_eval_cp = best_score.white().score(mate_score=10000)
        
        # Filter moves within eval window
        candidate_moves = []
        for line in multipv_lines:
            score = line.get("score")
            pv = line.get("pv")
            
            if not score or not pv:
                continue
                
            eval_cp = score.white().score(mate_score=10000)
            
            # Check if within window (accounting for perspective)
            eval_diff = abs(best_eval_cp - eval_cp)
            
            if eval_diff <= self.eval_window_cp:
                candidate_moves.append(pv[0])
        
        if not candidate_moves:
            # Fallback to best move
            return best_info.get("pv")[0] if best_info.get("pv") else random.choice(list(board.legal_moves))
        
        # Apply style bias
        if self.style == "neutral":
            return random.choice(candidate_moves)
            
        return self._select_by_style(board, candidate_moves)

    def _select_by_style(self, board: chess.Board, moves: List[chess.Move]) -> chess.Move:
        """
        Scores candidate moves based on the selected style.
        """
        scored_moves = []
        for move in moves:
            score = 0
            board.push(move)
            
            if self.style == "aggressive":
                # Prefers checks, attacks on royalty, or moving pieces closer to the enemy king
                if board.is_check(): score += 5
                # Simple heuristic: piece moving forward
                if board.turn == chess.BLACK: # If it's now White's turn, we just moved a Black piece
                    # No, board.turn flips after push. So if we just moved Black, board.turn is now WHITE.
                    # Black pieces move from high rank to low rank
                    if move.to_square < move.from_square: score += 2
            
            elif self.style == "passive":
                # Prefers defensive moves, avoiding checks, maintaining tension
                if not board.is_check(): score += 2
                # Avoiding king exposure
                if move.from_square in [chess.F1, chess.G1, chess.H1, chess.F8, chess.G8, chess.H8]: score -= 3
            
            elif self.style == "positional":
                # Prefers centralized pieces, development, pawn structure
                center_squares = [chess.D4, chess.E4, chess.D5, chess.E5]
                if move.to_square in center_squares: score += 3
                # Developing minor pieces
                if board.piece_at(move.to_square).piece_type in [chess.KNIGHT, chess.BISHOP]:
                    if move.from_square in [chess.B1, chess.G1, chess.B8, chess.G8]: score += 4

            board.pop()
            scored_moves.append((score, move))
            
        # Select from top scoring moves
        scored_moves.sort(key=lambda x: x[0], reverse=True)
        top_score = scored_moves[0][0]
        best_candidates = [m for s, m in scored_moves if s == top_score]
        
        return random.choice(best_candidates)
