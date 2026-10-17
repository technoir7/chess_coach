"""Builds the fixed set of positions every model is measured on.

    python -m evals.positions --round 2

Positions come from games the coach's own opponent plays against itself at club
strength, so each has a real move history behind it, as in the app. Each
position's engine analysis and prompt are stored with it: Stockfish does not
return identical lines on every search, and every model must explain the same
facts. Run once; the file is committed and never regenerated for a comparison.
"""

import argparse
import json
import random
import sys
from pathlib import Path
from pathlib import Path
from typing import List

import chess

from evals.score import round_argument, round_dir

COUNT = 100
FIRST_SEED = 2026  # round 1; each later round adds one
MAX_PLIES = 120
# The coach explains on the player's turn, and the player is always White.
FIRST_PLY, LATE_PLY = 6, 30
# The games only supply realistic positions; each is then analysed at the coach's
# full depth. At the coach's depth one game took six minutes.
PLAYER_DEPTH = 8


def positions_path(number: int) -> Path:
    return round_dir(number) / "positions.jsonl"


def pick_plies(length: int, rng: random.Random) -> List[int]:
    """One position from before move 15 and one from after, both White to move.

    `length` is how many plies the game lasted; a position at ply `p < length`
    had a move played from it, so the game was not over there.
    """
    early = list(range(FIRST_PLY, min(LATE_PLY, length), 2))
    late = list(range(LATE_PLY, length, 2))
    return [rng.choice(plies) for plies in (early, late) if plies]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    round_argument(parser)
    parser.add_argument("--count", type=int, default=COUNT)
    args = parser.parse_args()
    positions_file = positions_path(args.round)
    if positions_file.exists():
        sys.exit(f"{positions_file} exists; the comparison depends on it staying fixed.")
    seed = FIRST_SEED + args.round - 1

    from src.coach.coach import ChessCoach
    from src.engine.stockfish import AnalysisEngine
    from src.opponent.policy import OpponentPolicy
    from src.utils.config import load_config
    from src.utils.paths import repo_path

    random.seed(seed)  # the opponent policy samples with the module-level generator
    rng = random.Random(seed)

    coach = ChessCoach(load_config(repo_path("system_config.yaml")))
    coach.start()
    player_engine = AnalysisEngine(depth=PLAYER_DEPTH)
    player_engine.start()
    player = OpponentPolicy(player_engine, difficulty="club")
    positions = []
    try:
        game = 0
        while len(positions) < args.count:
            game += 1
            board = chess.Board()
            while not board.is_game_over() and len(board.move_stack) < MAX_PLIES:
                board.push(player.select_move(board))
            moves = [move.uci() for move in board.move_stack]

            for ply in pick_plies(len(moves), rng):
                position = chess.Board()
                for uci in moves[:ply]:
                    position.push_uci(uci)
                coach.board = position
                packet = coach.build_truth_packet()
                positions.append({
                    "id": f"p{len(positions) + 1:03d}",
                    "game": game,
                    "ply": ply,
                    "moves": moves[:ply],
                    "fen": position.fen(),
                    "eval_cp": packet.engine_eval,
                    "lines": [line.line_san for line in packet.candidate_lines],
                    "prompt": coach.explain_prompt(packet),
                })
                print(f"{positions[-1]['id']}  game {game}  ply {ply}", flush=True)
    finally:
        coach.stop()
        player_engine.stop()

    positions_file.parent.mkdir(exist_ok=True)
    positions_file.write_text("".join(json.dumps(p) + "\n" for p in positions[:args.count]))


if __name__ == "__main__":
    main()
