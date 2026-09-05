import chess
import os
from typing import Optional, Dict
from src.models import SystemConfig, TruthPacket, CoachSpeechRules
from src.coach.opening_db import OpeningDB
from src.engine.stockfish import AnalysisEngine
from src.engine.leela import IntuitionEngine
from src.coach.gate import LogicGate
from src.coach.llm import LLMClient
from src.opponent.policy import OpponentPolicy
from src.utils.paths import repo_path

# lc0 silently falls back to whichever net ships with the build when no weights
# are given, so the default belongs here rather than only in start_server.sh.
DEFAULT_LEELA_WEIGHTS = repo_path("maia-1500.pb.gz")


class BerkeleyChaosChessCoach:
    def __init__(self, config: SystemConfig, engine_path: str = "stockfish"):
        self.config = config
        if str(config.engines.analysis_engine.depth_policy) == "fixed":
            # Default fixed depth if policy is "fixed"
            self.depth = 15 
        else:
             # Try to parse or fallback
            try:
                self.depth = int(config.engines.analysis_engine.depth_policy)
            except (ValueError, TypeError):
                self.depth = 15

        self.engine = AnalysisEngine(
            engine_path=engine_path, 
            depth=self.depth
        )
        # Initialize Intuition Engine (Lc0)
        # Note: We use 'lc0' as default path, but users can override
        self.intuition_engine = IntuitionEngine(
            engine_path=os.getenv("LEELA_ENGINE_PATH", "lc0"),
            weights_path=os.getenv("LEELA_WEIGHTS_PATH", DEFAULT_LEELA_WEIGHTS)
        )
        self.opening_db = OpeningDB() # Initialize opening database
        self.gate = LogicGate(config.logic_gate)
        self.llm = LLMClient(model_name=config.llm.model)
        self.opponent = OpponentPolicy(self.engine, difficulty="club")  # Default to club level
        self.board = chess.Board()
        self.previous_eval: Optional[float] = None
        self.player_color = chess.WHITE  # User plays White by default
        self._theme_cache = {}  # Cache for position themes to save API quota
        self._last_quota_error = 0  # Timestamp of last 429 error
        self._cooldown_period = 5  # Reduced to 5 seconds for faster recovery

    def start(self):
        self.engine.start()
        try:
            self.intuition_engine.start()
        except Exception as e:
            # Don't crash if Leela fails, it's 'intuition only' for now
            print(f"Warning: Could not start Leela engine: {e}")

    def stop(self):
        self.engine.stop()
        self.intuition_engine.stop()

    def process_move(self, move_uci: str) -> Dict[str, str]:
        """
        Process a user's move, update state, run analysis, and potentially return advice.
        """
        # 1. Apply move
        try:
            move = chess.Move.from_uci(move_uci)
            if move in self.board.legal_moves:
                user_san = self.board.san(move) # Get SAN before pushing
                self.board.push(move)
            else:
                return {"error": "Illegal move"}
        except ValueError:
             return {"error": "Invalid UCI format"}

        # 2. Run Analysis (on new position)
        # Note: In a real game, we might analyze BEFORE the opponent moves, 
        # but here we analyze the position ON THE BOARD (after user move, or before user move?)
        # "Coach" usually advises on the current position or reacts to the previous move.
        # Let's assume we analyze the position AFTER the user moved to see if they messed up.
        
        analysis = self.engine.analyze(self.board)
        current_eval = analysis.get("eval_cp")
        
        # 2b. Run Intuition Analysis
        leela_vibe = self.intuition_engine.get_vibe(self.board)
        
        # 3. Construct Truth Packet
        packet = TruthPacket(
            fen=self.board.fen(),
            engine_eval=current_eval,
            multipv_lines=analysis.get("multipv_lines", []),
            opponent_threats=[], # TODO: Implement threat detection
            chaos_score=0.0, # TODO: Implement Chaos metric
            game_phase="middlegame" # Placeholder
        )
        # You could also add leela_vibe here if you extend TruthPacket model

        # 4. Logic Gate
        advice = None
        if self.gate.should_advise(packet, self.previous_eval):
            advice = self.llm.generate_advice(packet, self.config.coach_speech_rules)

        self.previous_eval = current_eval
        
        result = {
            "fen": self.board.fen(),
            "eval": str(current_eval),
            "user_move_san": user_san,
        }
        if advice:
            result["advice"] = advice

        # 5. If it's opponent's turn, make opponent move
        if self.board.turn != self.player_color:
            opponent_move = self.opponent.select_move(self.board)
            opp_san = self.board.san(opponent_move) # Get SAN before pushing
            self.board.push(opponent_move)
            result["opponent_move"] = opponent_move.uci()
            result["opponent_move_san"] = opp_san
            result["fen_after_opponent"] = self.board.fen()
        return result
    
    def _check_llm_available(self) -> bool:
        """Check if LLM is enabled and not in cooldown"""
        import time
        if not self.llm.model:
            return False
            
        # Check if we are in a cooldown period after a 429
        if time.time() - self._last_quota_error < self._cooldown_period:
            return False
            
        return True

    def _handle_quota_error(self, error_msg: str):
        """Register a quota error and start cooldown"""
        import time
        print(f"[Coach] LLM error hit: {error_msg}. Entering short cooldown.")
        self._last_quota_error = time.time()
    
    def reset_cooldown(self):
        """Reset the LLM cooldown"""
        self._last_quota_error = 0

    def _get_piece_listing(self) -> str:
        """Generate explicit listing of all pieces for LLM clarity"""
        piece_map = self.board.piece_map()
        white_pieces = []
        black_pieces = []
        
        for square, piece in piece_map.items():
            square_name = chess.square_name(square)
            piece_name = piece.symbol().upper()
            piece_names = {
                'P': 'Pawn', 'N': 'Knight', 'B': 'Bishop', 
                'R': 'Rook', 'Q': 'Queen', 'K': 'King'
            }
            full_name = piece_names.get(piece_name, piece_name)
            
            if piece.color == chess.WHITE:
                white_pieces.append(f"{full_name} on {square_name}")
            else:
                black_pieces.append(f"{full_name} on {square_name}")
        
        listing = "White pieces: " + ", ".join(sorted(white_pieces)) + "\n"
        listing += "Black pieces: " + ", ".join(sorted(black_pieces))
        return listing

    def _get_legal_moves_list(self) -> str:
        """Generate comma-separated list of all legal SAN moves"""
        # Create a temporary board to ensure we get SAN correctly
        # (though self.board should be fine, we want to be safe with move generation)
        legal_moves = []
        for move in self.board.legal_moves:
            legal_moves.append(self.board.san(move))
        
        return ", ".join(sorted(legal_moves))
    
    def _get_opening_info(self, fen: str) -> str:
        """Fetch and format opening info for the prompt"""
        data = self.opening_db.get_opening(fen)
        if not data or not data.get("name"):
            return "OPENING: Unknown / Custom position"
            
        info = f"OPENING: {data['name']} ({data.get('eco', '')})\n"
        info += "MASTER MOVES:\n"
        for m in data.get("moves", [])[:3]:
            # Calculate percentages
            total = m["total"]
            if total > 0:
                w_pct = int(m["white"] / total * 100)
                d_pct = int(m["draw"] / total * 100)
                b_pct = int(m["black"] / total * 100)
                info += f"- {m['san']}: White {w_pct}%, Draw {d_pct}%, Black {b_pct}% ({total} games)\n"
        return info

    def explain_position(self) -> str:
        """
        Generates a detailed explanation of the current position.
        Uses both engines and the LLM to provide insights.
        """
        # Analyze current position
        analysis = self.engine.analyze(self.board)
        current_eval = analysis.get("eval_cp")
        leela_vibe = self.intuition_engine.get_vibe(self.board)
        
        # Get top moves in SAN notation (human-readable)
        top_moves_san = []
        for line in analysis.get('multipv_lines', [])[:3]:
            pv = line.get('pv')
            if pv:
                # Clone board to safely convert UCI to SAN
                temp_board = self.board.copy()
                try:
                    move = temp_board.parse_uci(str(pv[0]))
                    top_moves_san.append(temp_board.san(move))
                except:
                    pass
        
        move_count = len(self.board.move_stack)
        game_phase = "Opening" if move_count < 15 else ("Middlegame" if move_count < 40 else "Endgame")
        
        # Build explanation prompt
        explanation_prompt = f"""
You are a chess coach analyzing this position.

GAME STATE: Move {move_count} - {game_phase} phase

CURRENT POSITION:
{self._get_piece_listing()}

{self._get_opening_info(self.board.fen())}

LEGAL MOVES (STRICTLY ENFORCED):
{self._get_legal_moves_list()}

Stockfish Evaluation: {current_eval} centipawns
Leela Vibe Score: {leela_vibe.get('vibe_score', 'N/A')}
Top Moves: {', '.join(top_moves_san)}

EVALUATION SCALE (Centipawns):
- 0 to 40: Equal / Normal opening edge
- 41 to 100: Slight advantage
- 101 to 250: Clear/Significant advantage
- 251+: Decisive advantage / Winning

INSTRUCTIONS:
1. Use the scale above to describe the evaluation. Do NOT call +36cp "significant".
2. Before mentioning a piece on a square, verify it exists in the position listing above.
3. LEGAL MOVES CHECK: You MUST NOT suggest any move for the current player that is NOT in the "LEGAL MOVES" list above.
   - If a move you want to suggest is not in that list, IT IS ILLEGAL (e.g. piece is pinned).
   - Do NOT say "Black can capture..." if the capture is not in the legal moves list.

4. CRITICAL - NO CALCULATING VARIATIONS:
   - You CANNOT calculate multi-move sequences yourself. You will hallucinate.
   - Do NOT write lines like "1. Bxb5 Qxb5 2. Bxd7+ Kxd7 3. Qxc7+" - you WILL get this wrong.
   - ONLY mention the engine's "Top Moves" above. Do NOT invent follow-up moves.
   - If asked "what happens after X?", say "I recommend checking the engine analysis for that line."
   - Focus on describing the CURRENT position, themes, and piece activity.

Provide a concise, accurate explanation of the current position only.
"""
        
        if self._check_llm_available():
            try:
                response = self.llm.generate_content(explanation_prompt)
                return response.text
            except Exception as e:
                # Log the full error for debugging
                print(f"[Coach Debug] Full LLM Error: {type(e).__name__}: {str(e)}")
                
                if "429" in str(e) or "quota" in str(e).lower():
                    self._handle_quota_error(str(e))
                
                eval_text = self._get_eval_text(current_eval)
                fallback_moves = ", ".join(top_moves_san) if top_moves_san else "N/A"
                return f"Coach (Offline): {eval_text} ({current_eval}cp). \nBest follows: {fallback_moves} \n(Reason: {str(e)[:100]})"
        else:
            reason = "Cooldown (quota exceeded)" if self._last_quota_error > 0 else "LLM Disabled"
            eval_text = self._get_eval_text(current_eval)
            fallback_moves = ", ".join(top_moves_san) if top_moves_san else "N/A"
            return f"Coach (Offline): {eval_text} ({current_eval}cp). \nBest follows: {fallback_moves} \n(Reason: {reason})"

    def chat(self, message: str) -> str:
        """
        Handles interactive chat about the position.
        """
        analysis = self.engine.analyze(self.board)
        current_eval = analysis.get("eval_cp")
        leela_vibe = self.intuition_engine.get_vibe(self.board)
        
        # Get top moves in SAN notation
        top_moves_san = []
        for line in analysis.get('multipv_lines', [])[:3]:
            pv = line.get('pv')
            if pv:
                temp_board = self.board.copy()
                try:
                    move = temp_board.parse_uci(str(pv[0]))
                    top_moves_san.append(temp_board.san(move))
                except:
                    pass
        
        # Get move history in SAN notation with correct numbering
        move_history_lines = []
        if len(self.board.move_stack) > 0:
            # Create a copy and pop last 10 moves to get to past state
            temp_board = self.board.copy()
            last_moves = []
            num_moves_to_show = min(10, len(self.board.move_stack))
            
            for _ in range(num_moves_to_show):
                last_moves.append(temp_board.pop())
            
            # Now play them forward
            last_moves.reverse() # Oldest first
            
            current_line = ""
            for i, move in enumerate(last_moves):
                # Calculate move number
                move_num = temp_board.fullmove_number
                san = temp_board.san(move)
                
                if temp_board.turn == chess.WHITE:
                    current_line = f"{move_num}. {san}"
                else:
                    if current_line:
                        current_line += f" {san}"
                        move_history_lines.append(current_line)
                        current_line = ""
                    else:
                        # Started with black move (e.g. at start of history window)
                        move_history_lines.append(f"{move_num}. ... {san}")
                
                temp_board.push(move)
            
            # Append trailing white move if any
            if current_line:
                move_history_lines.append(current_line)

        history_str = "\n".join(move_history_lines) if move_history_lines else "Game just started"

        move_count = len(self.board.move_stack)
        game_phase = "Opening" if move_count < 15 else ("Middlegame" if move_count < 40 else "Endgame")
        
        chat_prompt = f"""
You are an interactive chess coach. The user is asking about the current position.

GAME STATE: Move {move_count} - {game_phase} phase

CURRENT POSITION:
{self._get_piece_listing()}

{self._get_opening_info(self.board.fen())}

LEGAL MOVES (STRICTLY ENFORCED):
{self._get_legal_moves_list()}

Stockfish Eval: {current_eval}cp
Leela Vibe: {leela_vibe.get('vibe_score', 'N/A')}
Top Engine Moves: {', '.join(top_moves_san) if top_moves_san else 'N/A'}

RECENT MOVES:
{history_str}

EVALUATION SCALE (Centipawns):
- 0 to 40: Equal / Normal opening edge
- 41 to 100: Slight advantage
- 101 to 250: Clear/Significant advantage
- 251+: Decisive advantage / Winning

User's Question: {message}

INSTRUCTIONS:
1. Use the scale above for your language. +36cp is "Equal" or "Slight white edge", NOT significant.
2. Before claiming any piece is on a square, verify it exists in the position listing above.
3. LEGAL MOVES CHECK: You MUST NOT suggest any move for the current player that is NOT in the "LEGAL MOVES" list above.
   - If a move is not listed, it is illegal (pinned, blocked, etc.). Do not suggest it.

4. CRITICAL - NO CALCULATING VARIATIONS:
   - You CANNOT calculate multi-move sequences yourself. You will hallucinate.
   - Do NOT write lines like "1. Bxb5 Qxb5 2. Bxd7+ Kxd7 3. Qxc7+" - you WILL invent pieces or moves.
   - ONLY mention the engine's "Top Engine Moves" above. Do NOT invent follow-up moves.
   - If asked "what happens after X?", say "I can't reliably calculate lines. The engine's top moves are..."
   - Focus on describing the CURRENT position, themes, and piece activity.

Provide a helpful, accurate response about the current position only.
"""
        if self._check_llm_available():
            try:
                response = self.llm.generate_content(chat_prompt)
                return response.text
            except Exception as e:
                if "429" in str(e):
                    self._handle_quota_error(str(e))
                return f"Coach: I'm focusing on the game right now (Offline). (Error: {str(e)[:50]})"
        return "Coach: I'm taking a short break from talking (Offline). I'll be back in a minute!"
    
    def get_position_theme(self) -> str:
        """
        Returns a concise one-line positional assessment.
        Uses a cache to save API quota.
        """
        fen = self.board.fen()
        # Clean FEN to ignore move counters for better caching
        fen_parts = fen.split()
        fen_key = " ".join(fen_parts[:3]) # Ignore castling too if we want broader themes
        
        if fen_key in self._theme_cache:
            return self._theme_cache[fen_key]

        if self._check_llm_available():
            try:
                analysis = self.engine.analyze(self.board)
                current_eval = analysis.get("eval_cp")
                
                prompt = f"""
Chess coach: 3 word positional theme for FEN: {fen} (Eval: {current_eval})
Example: "Closed tactical middlegame"
Respond ONLY with the theme.
"""
                response = self.llm.generate_content(prompt)
                theme = response.text.strip().replace('"', '')
                self._theme_cache[fen_key] = theme
                return theme
            except Exception as e:
                if "429" in str(e):
                    self._handle_quota_error(str(e))
                
                analysis = self.engine.analyze(self.board)
                return self._get_basic_theme(analysis.get("eval_cp"))
        
        # Fallback: Basic heuristic
        analysis = self.engine.analyze(self.board)
        return self._get_basic_theme(analysis.get("eval_cp"))

    def _get_eval_text(self, cp: Optional[float]) -> str:
        """Converts centipawns to human-readable chess terms"""
        if cp is None: return "Evaluation unclear"
        
        abs_cp = abs(cp)
        if abs_cp <= 40: return "The position is equal"
        
        prefix = "White" if cp > 0 else "Black"
        if abs_cp > 250: return f"{prefix} is winning decisively"
        if abs_cp > 100: return f"{prefix} has a significant advantage"
        if abs_cp > 40: return f"{prefix} is slightly better"
        return "Position is complex"

    def _get_basic_theme(self, cp: Optional[float] = None) -> str:
        """Human-readable theme fallback when LLM is unavailable"""
        board = self.board
        
        # Use eval to inform theme
        if cp is not None:
            if cp > 300 or cp < -300: return "Decisive material balance"
            if abs(cp) > 150: return "Clear positional advantage"
        
        # Opening
        if len(board.move_stack) < 10:
            return "Opening development"
        
        # Endgame
        piece_count = len(board.piece_map())
        if piece_count <= 10:
            return "Endgame technique"
        
        # Check for checks
        if board.is_check():
            return "Tactical complications"
        
        # Default
        return "Middlegame maneuvering"
    
    def get_board_visual(self) -> str:
        return str(self.board)
