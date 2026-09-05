import chess
import os
from typing import Optional, Dict, List
from src.models import SystemConfig, TruthPacket, CoachSpeechRules
from src.coach import prompts
from src.coach.opening_db import OpeningDB
from src.coach.threats import detect_threats
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
        self._previous_packet: Optional[TruthPacket] = None
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
        
        packet = self.build_truth_packet()
        current_eval = packet.engine_eval

        # 4. Logic Gate
        advice = None
        if self.gate.should_advise(packet, self._previous_packet):
            advice = self._generate_advice(packet)

        self._previous_packet = packet
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

    def _generate_advice(self, packet: TruthPacket) -> Optional[str]:
        """Short in-game advice, grounded in the packet the gate just approved."""
        if not self._check_llm_available():
            return None

        prompt = prompts.advice_prompt(
            self._facts_block(packet), self.config.coach_speech_rules
        )
        try:
            return self.llm.generate_content(prompt).text
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                self._handle_quota_error(str(e))
            return None

    def opponent_accepts_draw(self) -> bool:
        """Whether the opponent accepts a draw in the current position."""
        return self.opponent.accepts_draw(self.board)

    def build_truth_packet(self) -> TruthPacket:
        """Run both engines and collect the verified facts for this position.

        This is the only place engine output enters the coach, so everything
        downstream - the logic gate and every prompt - reads the same facts.
        """
        analysis = self.engine.analyze(self.board)
        vibe = self.intuition_engine.get_vibe(self.board)

        return TruthPacket(
            fen=self.board.fen(),
            engine_eval=analysis.get("eval_cp"),
            multipv_lines=analysis.get("multipv_lines", []),
            opponent_threats=detect_threats(self.board, self.player_color),
            chaos_score=0.0,  # TODO: Implement Chaos metric
            game_phase=prompts.game_phase(self.board),
            vibe_score=vibe.get("vibe_score"),
            top_moves_san=self._top_moves_san(analysis),
        )

    def _top_moves_san(self, analysis: Dict) -> List[str]:
        """Convert the engine's principal variations to SAN."""
        moves = []
        for line in analysis.get("multipv_lines", [])[:3]:
            pv = line.get("pv")
            if pv:
                board = self.board.copy()
                moves.append(board.san(board.parse_uci(str(pv[0]))))
        return moves

    def _facts_block(self, packet: TruthPacket) -> str:
        """Render a packet into the prompt's verified-facts section."""
        return prompts.position_facts(
            self.board, packet, self._get_opening_info(self.board.fen())
        )

    def _get_opening_info(self, fen: str) -> str:
        """Fetch and format opening info for the prompt"""
        data = self.opening_db.get_opening(fen)
        if not data or not data.get("name"):
            # Never describe the position as unknown or custom: the model reads
            # that as licence to call a standard opening "unusual".
            return ("OPENING: Not in the opening book. "
                    "Do not comment on whether it is common or unusual.")

        info = f"OPENING: {data['name']} ({data.get('eco', '')})\n"

        moves = data.get("moves", [])[:3]
        if moves:
            info += "MASTER MOVES:\n"
            for m in moves:
                # Calculate percentages
                total = m["total"]
                if total > 0:
                    w_pct = int(m["white"] / total * 100)
                    d_pct = int(m["draw"] / total * 100)
                    b_pct = int(m["black"] / total * 100)
                    info += f"- {m['san']}: White {w_pct}%, Draw {d_pct}%, Black {b_pct}% ({total} games)\n"
        return info

    def explain_position(self) -> str:
        """Explain the current position, grounded in the Truth Packet."""
        packet = self.build_truth_packet()

        if not self._check_llm_available():
            reason = "Cooldown (quota exceeded)" if self._last_quota_error > 0 else "LLM Disabled"
            return self._offline_summary(packet, reason)

        try:
            prompt = prompts.explain_prompt(self._facts_block(packet))
            return self.llm.generate_content(prompt).text
        except Exception as e:
            print(f"[Coach Debug] Full LLM Error: {type(e).__name__}: {str(e)}")
            if "429" in str(e) or "quota" in str(e).lower():
                self._handle_quota_error(str(e))
            return self._offline_summary(packet, str(e)[:100])

    def _offline_summary(self, packet: TruthPacket, reason: str) -> str:
        """Engine-only fallback when the LLM is unavailable."""
        moves = ", ".join(packet.top_moves_san) if packet.top_moves_san else "N/A"
        return (
            f"Coach (Offline): {self._get_eval_text(packet.engine_eval)} "
            f"({packet.engine_eval}cp). \nBest follows: {moves} \n(Reason: {reason})"
        )

    def chat(self, message: str) -> str:
        """Answer a question about the position, grounded in the Truth Packet."""
        if not self._check_llm_available():
            return "Coach: I'm taking a short break from talking (Offline). I'll be back in a minute!"

        packet = self.build_truth_packet()
        prompt = prompts.chat_prompt(
            self._facts_block(packet), prompts.recent_moves(self.board), message
        )

        try:
            return self.llm.generate_content(prompt).text
        except Exception as e:
            if "429" in str(e):
                self._handle_quota_error(str(e))
            return f"Coach: I'm focusing on the game right now (Offline). (Error: {str(e)[:50]})"
    
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

        current_eval = self.engine.analyze(self.board).get("eval_cp")

        if self._check_llm_available():
            try:
                response = self.llm.generate_content(prompts.theme_prompt(fen, current_eval))
                theme = response.text.strip().replace('"', '')
                self._theme_cache[fen_key] = theme
                return theme
            except Exception as e:
                if "429" in str(e):
                    self._handle_quota_error(str(e))

        return self._get_basic_theme(current_eval)

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
