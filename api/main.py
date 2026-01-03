from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import sys
import os
import datetime
from fastapi import FastAPI, HTTPException, Response

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.models import MoveRequest, GameState, ExplainResponse, ChatRequest, OpponentSettings
from api.game_manager import GameManager

app = FastAPI(title="BerkeleyChaosChessCoach API")

# CORS configuration for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for web frontend
web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
if os.path.exists(web_dir):
    app.mount("/static", StaticFiles(directory=os.path.join(web_dir, "static")), name="static")

# Global game manager
game_manager = GameManager()

@app.get("/")
async def root():
    """Serve the main web page"""
    from fastapi.responses import FileResponse
    index_path = os.path.join(web_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "BerkeleyChaosChessCoach API", "docs": "/docs"}

@app.post("/api/game/new")
async def create_game() -> dict:
    """Create a new game session"""
    game_id = game_manager.create_game()
    session = game_manager.get_game(game_id)
    return session.get_state_dict()

@app.get("/api/models")
async def get_models() -> dict:
    """Get list of available LLM models"""
    from src.coach.llm import LLMClient
    # Instantiate client just to fetch models
    client = LLMClient() 
    return client.get_available_models()

@app.get("/api/game/{game_id}")
async def get_game(game_id: str) -> dict:
    """Get current game state"""
    try:
        session = game_manager.get_game(game_id)
        return session.get_state_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/game/{game_id}/move")
async def make_move(game_id: str, move_request: MoveRequest) -> dict:
    """Make a move in the game"""
    try:
        session = game_manager.get_game(game_id)
        
        # Process the move
        result = session.coach.process_move(move_request.move)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Add to move history (UCI)
        session.move_history.append(move_request.move)
        
        # Log User Event (with SAN and Advice)
        session.events.append({
            "role": "user",
            "move_san": result.get("user_move_san", move_request.move),
            "advice": result.get("advice")
        })

        if "opponent_move" in result:
            session.move_history.append(result["opponent_move"])
            # Log Opponent Event
            session.events.append({
                "role": "opponent",
                "move_san": result.get("opponent_move_san", result["opponent_move"]),
                "advice": None
            })
        
        # Return updated state
        state = session.get_state_dict()
        state["advice"] = result.get("advice")
        state["opponent_move"] = result.get("opponent_move")
        
        return state
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/game/{game_id}/explain")
async def explain_position(game_id: str) -> ExplainResponse:
    """Get position explanation"""
    try:
        session = game_manager.get_game(game_id)
        explanation = session.coach.explain_position()
        
        # Get current analysis
        analysis = session.coach.engine.analyze(session.coach.board)
        
        return ExplainResponse(
            explanation=explanation,
            eval_cp=analysis.get("eval_cp"),
            top_moves=[str(line.get('pv', [''])[0]) for line in analysis.get('multipv_lines', [])[:3] if line.get('pv')]
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/game/{game_id}/chat")
async def chat_with_coach(game_id: str, chat_request: ChatRequest) -> dict:
    """Interact with the coach via chat"""
    try:
        session = game_manager.get_game(game_id)
        response = session.coach.chat(chat_request.message)
        return {"response": response}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/game/{game_id}/settings")
async def update_settings(game_id: str, settings: OpponentSettings) -> dict:
    """Update opponent settings"""
    try:
        session = game_manager.get_game(game_id)
        session.update_settings(settings.difficulty, settings.style, settings.model)
        return session.get_state_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/game/{game_id}/resign")
async def resign_game(game_id: str) -> dict:
    """Resign the game"""
    try:
        session = game_manager.get_game(game_id)
        session.resigned = True
        return session.get_state_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/game/{game_id}/draw/offer")
async def offer_draw(game_id: str) -> dict:
    """Offer a draw to the opponent"""
    try:
        session = game_manager.get_game(game_id)
        
        # Simple evaluation-based logic for draw acceptance
        analysis = session.coach.engine.analyze(session.coach.board)
        eval_cp = analysis.get("eval_cp", 0)
        move_count = len(session.coach.board.move_stack)
        
        accepted = False
        # Accept draw if position is dead equal and after opening
        if abs(eval_cp) < 50 and move_count > 20:
            accepted = True
            session.draw_agreed = True
            
        return {
            "accepted": accepted,
            "state": session.get_state_dict(),
            "message": "Draw accepted." if accepted else "Draw declined. The game continues."
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.delete("/api/game/{game_id}")
async def delete_game(game_id: str):
    """Delete a game session"""
    try:
        game_manager.cleanup_game(game_id)
        return {"message": "Game deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/game/{game_id}/export")
async def export_game(game_id: str):
    """Export game annotation as Markdown"""
    try:
        session = game_manager.get_game(game_id)
        
        # Build Markdown content
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        md_lines = [f"# Chess Game Analysis - {date_str}", ""]
        
        md_lines.append("## Move Log")
        md_lines.append("| Move | Annotation |")
        md_lines.append("|---|---|")
        
        move_num = 1
        for i, event in enumerate(session.events):
            role = event["role"]
            move = event["move_san"]
            advice = event.get("advice")
            
            # Format move label
            label = ""
            if role == "user":
                label = f"**{move_num}. {move}** (You)"
            else:
                label = f"**{move_num}. ... {move}** (Opponent)"
                move_num += 1
                
            # Format annotation
            annotation = advice.replace('\n', '<br>') if advice else "*No comment*"
            
            md_lines.append(f"| {label} | {annotation} |")
            
        content = "\n".join(md_lines)
        
        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=chess_game_{game_id[:8]}.md"}
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
