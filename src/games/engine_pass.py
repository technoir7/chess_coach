"""Stockfish over every position of many games, cached on disk.

About 0.17s a position at depth 16 on one core, so several hundred games
(tens of thousands of positions) take a quarter of an hour on 8 workers the
first time; the cache makes re-runs and new games cheap.
"""

import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import chess
import chess.engine

from src.games import move_review
from src.games.game import Game
from src.games.win_chances import Eval

PV_PLIES = 12
_engine: Optional[chess.engine.SimpleEngine] = None
_depth = 16


def terminal_eval(board: chess.Board) -> Optional[Eval]:
    """Finished positions have no engine search to run. A mate is scored
    as mate in one for the winner: only its sign is used."""
    if board.is_checkmate():
        return Eval(mate=-1 if board.turn == chess.WHITE else 1)
    if board.is_game_over():
        return Eval(cp=0)
    return None


def threat_fen(board: chess.Board) -> str:
    """The position with the opponent to move instead, to see what they
    threaten. Not valid when the side to move is in check."""
    passed = board.copy(stack=False)
    passed.push(chess.Move.null())
    return passed.fen()


class EvalCache:
    """Evaluations by position and depth, one JSON object per line."""

    def __init__(self, path: Path, depth: int):
        self.path, self.depth = Path(path), depth
        self._entries: Dict[str, Eval] = {}
        self._new: Dict[str, Eval] = {}
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                row = json.loads(line)
                if row["depth"] == depth:
                    self._entries[row["fen"]] = Eval(cp=row.get("cp"), mate=row.get("mate"), pv=tuple(row["pv"]))

    def get(self, fen: str) -> Optional[Eval]:
        return self._entries.get(fen)

    def put(self, fen: str, evaluation: Eval) -> None:
        self._entries[fen] = evaluation
        self._new[fen] = evaluation

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as out:
            for fen, e in self._new.items():
                out.write(json.dumps({"fen": fen, "depth": self.depth, "cp": e.cp,
                                      "mate": e.mate, "pv": list(e.pv)}) + "\n")
        self._new.clear()


def _start(engine_path: str, depth: int) -> None:
    global _engine, _depth
    _engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    _engine.configure({"Threads": 1, "Hash": 64})
    _depth = depth


def _to_eval(info: chess.engine.InfoDict) -> Eval:
    score = info["score"].white()
    pv = tuple(m.uci() for m in info.get("pv", [])[:PV_PLIES])
    if score.is_mate():
        return Eval(mate=score.mate(), pv=pv)
    return Eval(cp=score.score(), pv=pv)


def _search(fen: str) -> Tuple[str, Eval]:
    return fen, _to_eval(_engine.analyse(chess.Board(fen), chess.engine.Limit(depth=_depth)))


def _search_second(fen: str) -> Tuple[str, Eval]:
    """The engine's second choice."""
    infos = _engine.analyse(chess.Board(fen), chess.engine.Limit(depth=_depth), multipv=2)
    if len(infos) < 2:
        raise ValueError(f"only one legal move in {fen}")
    return fen, _to_eval(infos[1])


def evaluate(fens: Sequence[str], depth: int, workers: int,
             engine_path: Optional[str] = None, search: Callable = _search) -> List[Eval]:
    """Search each live position; one Stockfish per worker process."""
    engine_path = engine_path or os.getenv("CHESS_ENGINE_PATH", "stockfish")
    results: Dict[str, Eval] = {}
    with Pool(workers, initializer=_start, initargs=(engine_path, depth)) as pool:
        for done, (fen, evaluation) in enumerate(pool.imap_unordered(search, fens, chunksize=16), 1):
            results[fen] = evaluation
            if done % 2000 == 0:
                print(f"  {done}/{len(fens)} positions", file=sys.stderr)
    return [results[fen] for fen in fens]


def _fill(cache: EvalCache, boards: Iterable[Tuple[str, chess.Board]], depth: int, workers: int) -> None:
    missing = {}
    for fen, board in boards:
        if cache.get(fen) is not None or fen in missing:
            continue
        finished = terminal_eval(board)
        if finished is not None:
            cache.put(fen, finished)
        else:
            missing[fen] = board
    if missing:
        print(f"Analysing {len(missing)} positions at depth {depth}...", file=sys.stderr)
        for fen, evaluation in zip(missing, evaluate(list(missing), depth, workers)):
            cache.put(fen, evaluation)
    cache.save()


def analyse_games(games: Sequence[Game], cache: EvalCache, workers: int
                  ) -> Dict[str, Tuple[List[Eval], Dict[int, Eval]]]:
    """For each game: an eval per position, and the threat eval at each of
    the player's mistakes where they weren't in check."""
    boards = {g.id: g.boards() for g in games}
    _fill(cache, ((b.fen(), b) for bs in boards.values() for b in bs), cache.depth, workers)
    evals = {g.id: [cache.get(b.fen()) for b in boards[g.id]] for g in games}

    threat_boards = {}
    for g in games:
        for ply in move_review.candidate_plies(g, evals[g.id]):
            board = boards[g.id][ply]
            if not board.is_check():
                threat_boards[(g.id, ply)] = threat_fen(board)
    _fill(cache, ((fen, chess.Board(fen)) for fen in threat_boards.values()), cache.depth, workers)

    return {
        g.id: (evals[g.id], {ply: cache.get(fen) for (gid, ply), fen in threat_boards.items() if gid == g.id})
        for g in games
    }


def second_bests(fens: Sequence[str], cache: EvalCache, workers: int) -> List[Eval]:
    """The engine's second choice in each position, with `cache` holding
    second choices only (keep it apart from the main one)."""
    missing = [fen for fen in dict.fromkeys(fens) if cache.get(fen) is None]
    if missing:
        for fen, evaluation in zip(missing, evaluate(missing, cache.depth, workers, search=_search_second)):
            cache.put(fen, evaluation)
        cache.save()
    return [cache.get(fen) for fen in fens]
