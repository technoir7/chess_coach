from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from src.coach.coach import BerkeleyChaosChessCoach
import sys

console = Console()

class ChessCLI:
    def __init__(self, coach: BerkeleyChaosChessCoach):
        self.coach = coach

    def run(self):
        console.print(Panel.fit("Berkeley Chaos Chess Coach", style="bold magenta"))
        
        try:
            self.coach.start()
        except Exception as e:
            console.print(f"[bold red]Failed to start engine:[/bold red] {e}")
            return

        while True:
            # Display Board
            board_str = self.coach.get_board_visual()
            console.print(board_str)
            
            # Input
            user_input = Prompt.ask("Enter move (UCI, e.g. e2e4), 'explain' for analysis, or 'q' to quit")
            
            if user_input.lower() in ['q', 'quit', 'exit']:
                break
            
            if user_input.lower() == 'explain':
                with console.status("Analyzing position..."):
                    explanation = self.coach.explain_position()
                console.print(Panel(explanation, title="Position Analysis", style="bold cyan"))
                continue
            
            # Process move
            with console.status("Thinking..."):
                result = self.coach.process_move(user_input)
            
            # Output
            if "error" in result:
                console.print(f"[bold red]Error:[/bold red] {result['error']}")
            else:
                eval_str = result.get("eval", "N/A")
                console.print(f"[blue]Eval:[/blue] {eval_str}")
                
                if "advice" in result:
                    console.print(Panel(result["advice"], title="Coach Says", style="bold yellow"))
                
                # Show opponent move if present
                if "opponent_move" in result:
                    console.print(f"[bold green]Opponent plays:[/bold green] {result['opponent_move']}")

        self.coach.stop()
        console.print("Goodbye!")
