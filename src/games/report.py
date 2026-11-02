"""Where a player's games go wrong, summed over many games."""

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import chess

from src.games.move_review import (ALLOWED_TACTIC, BLUNDER, MISSED_TACTIC, MISSED_THREAT, MISTAKE,
                                   QUIET, MoveRecord, ReviewedGame)
from src.games.win_chances import Eval, win_percent

SPEEDS = ("bullet", "blitz", "rapid", "classical")
LOW_CLOCK = "low_clock"
WINNING = 80.0  # about +3.8: a clear piece up
OPENING_PLY = 20  # the position after Black's 10th move

KIND_LABELS = {
    MISSED_THREAT: ("Missed their threat",
                    "they already threatened something, your move ignored it, and they played it"),
    ALLOWED_TACTIC: ("Gave them a tactic", "your move handed over material or a mate"),
    MISSED_TACTIC: ("Missed your tactic", "you had a move that won material or mated, and played another"),
    QUIET: ("Quiet mistake", "no material changes hands soon: a positional error, or a tactic too deep for these checks"),
    LOW_CLOCK: ("Short of time", "any mistake made with under a tenth of the starting time (or 30s) left"),
}
KIND_ORDER = (MISSED_THREAT, ALLOWED_TACTIC, MISSED_TACTIC, QUIET, LOW_CLOCK)


@dataclass(frozen=True)
class SpeedRow:
    speed: str
    games: int
    score: float
    mistakes_per_game: float
    blunders_per_game: float
    lost_on_time: float


@dataclass(frozen=True)
class Conversion:
    reached: int
    won: int
    thrown: List[ReviewedGame]


@dataclass(frozen=True)
class ClockRates:
    low_moves: int
    low_mistakes: int
    normal_moves: int
    normal_mistakes: int


@dataclass(frozen=True)
class OpeningRow:
    name: str
    color: chess.Color
    games: int
    score: float
    win_chance_after_10: float


def _score(games: Sequence[ReviewedGame]) -> float:
    points = sum({"win": 1.0, "draw": 0.5}.get(g.game.result, 0.0) for g in games)
    return 100 * points / len(games)


def by_speed(games: Sequence[ReviewedGame]) -> List[SpeedRow]:
    groups = defaultdict(list)
    for g in games:
        groups[g.game.speed].append(g)
    rows = []
    for speed in SPEEDS:
        group = groups.get(speed)
        if not group:
            continue
        mistakes = [m for g in group for m in g.mistakes()]
        rows.append(SpeedRow(
            speed=speed,
            games=len(group),
            score=_score(group),
            mistakes_per_game=len(mistakes) / len(group),
            blunders_per_game=sum(m.is_blunder for m in mistakes) / len(group),
            lost_on_time=100 * sum(g.game.result == "loss" and g.game.termination == "outoftime"
                                   for g in group) / len(group),
        ))
    return rows


def _kind(record: MoveRecord) -> str:
    return LOW_CLOCK if record.low_clock else record.kind


def kind_counts(games: Sequence[ReviewedGame]) -> Dict[str, int]:
    """Mistakes by kind; those made short of time are counted apart, since
    the cure for them is the clock, not the chess."""
    return dict(Counter(_kind(m) for g in games for m in g.mistakes()))


def conversion(games: Sequence[ReviewedGame]) -> Conversion:
    reached = [g for g in games if max(win_percent(e, g.game.color) for e in g.evals) >= WINNING]
    won = [g for g in reached if g.game.result == "win"]
    return Conversion(len(reached), len(won), [g for g in reached if g.game.result != "win"])


def clock_rates(games: Sequence[ReviewedGame]) -> ClockRates:
    timed = [r for g in games for r in g.records if r.seconds_left is not None]
    low = [r for r in timed if r.low_clock]
    normal = [r for r in timed if not r.low_clock]
    return ClockRates(len(low), sum(r.kind is not None for r in low),
                      len(normal), sum(r.kind is not None for r in normal))


def openings(games: Sequence[ReviewedGame], minimum: int = 5) -> List[OpeningRow]:
    groups = defaultdict(list)
    for g in games:
        if len(g.evals) > OPENING_PLY:
            groups[(g.game.opening.split(":")[0], g.game.color)].append(g)
    rows = [
        OpeningRow(name, color, len(group), _score(group),
                   statistics.mean(win_percent(g.evals[OPENING_PLY], color) for g in group))
        for (name, color), group in groups.items() if len(group) >= minimum
    ]
    return sorted(rows, key=lambda r: r.win_chance_after_10)


def _move_label(record: MoveRecord) -> str:
    number = record.ply // 2 + 1
    return f"{number}.{'' if record.ply % 2 == 0 else '..'} {record.san}"


def _per(count: int, total: int) -> str:
    return f"{count / total:.2f}" if total else "-"


def _pct(count: int, total: int) -> str:
    return f"{100 * count / total:.0f}%" if total else "-"


def _median(values: List[float]) -> Optional[float]:
    return statistics.median(values) if values else None


def render(games: Sequence[ReviewedGame], username: str) -> str:
    out: List[str] = []
    dates = [g.game.played_at for g in games]
    all_mistakes = [m for g in games for m in g.mistakes()]
    out.append(f"# Game review: {username}\n")
    out.append(f"{len(games)} games from {min(dates):%b %Y} to {max(dates):%b %Y}, "
               f"{len(all_mistakes)} mistakes. Stockfish at depth 16 judged every position.\n")
    out.append(f"A **mistake** cuts your winning chances by {MISTAKE:.0f} points or more (Lichess's "
               f"\"mistake\"); a **blunder** by {BLUNDER:.0f} or more. Winning chances use Lichess's "
               "curve, so dropping 3 pawns in a won game counts for little and in an equal game for a lot.\n")

    out.append("## By time control\n")
    out.append("| | Games | Score | Mistakes per game | Blunders per game | Lost on time |")
    out.append("|---|---:|---:|---:|---:|---:|")
    for row in by_speed(games):
        out.append(f"| {row.speed} | {row.games} | {row.score:.0f}% | {row.mistakes_per_game:.1f} "
                   f"| {row.blunders_per_game:.1f} | {row.lost_on_time:.0f}% |")
    out.append("")

    out.append("## What kind of mistakes\n")
    out.append("Per game, by time control. Each mistake has one kind: the first in this list that fits.\n")
    groups = [(s, [g for g in games if g.game.speed == s]) for s in SPEEDS]
    groups = [(s, group) for s, group in groups if len(group) >= 10] + [("all", list(games))]
    out.append("| Kind | " + " | ".join(s for s, _ in groups) + " | Share of all |")
    out.append("|---" * (len(groups) + 2) + "|")
    totals = kind_counts(games)
    for kind in KIND_ORDER:
        label, _ = KIND_LABELS[kind]
        cells = [_per(kind_counts(group).get(kind, 0), len(group)) for _, group in groups]
        out.append(f"| {label} | " + " | ".join(cells) + f" | {_pct(totals.get(kind, 0), len(all_mistakes))} |")
    out.append("")
    for kind in KIND_ORDER:
        label, meaning = KIND_LABELS[kind]
        out.append(f"- **{label}**: {meaning}.")
    out.append("")

    out.append("## Clock\n")
    rates = clock_rates(games)
    out.append(f"- With time on the clock: {_pct(rates.normal_mistakes, rates.normal_moves)} of moves were mistakes "
               f"({rates.normal_mistakes} of {rates.normal_moves}).")
    out.append(f"- Short of time: {_pct(rates.low_mistakes, rates.low_moves)} "
               f"({rates.low_mistakes} of {rates.low_moves}).")
    out.append("")
    out.append("How long you took (median seconds), on moves made with time on the clock:\n")
    out.append("| | Every move | Mistakes | Missed their threat |")
    out.append("|---|---:|---:|---:|")
    for speed, group in groups:
        normal = [r for g in group for r in g.records if r.seconds_spent is not None and not r.low_clock]
        cells = [_median([r.seconds_spent for r in rs]) for rs in (
            normal, [r for r in normal if r.kind], [r for r in normal if r.kind == MISSED_THREAT])]
        out.append(f"| {speed} | " + " | ".join("-" if c is None else f"{c:.0f}" for c in cells) + " |")
    out.append("")

    out.append("## Game phase\n")
    out.append("| Phase | Your moves | Mistakes | Per 100 moves |")
    out.append("|---|---:|---:|---:|")
    for phase in ("Opening", "Middlegame", "Endgame"):
        moves = [r for g in games for r in g.records if r.phase == phase]
        count = sum(r.kind is not None for r in moves)
        out.append(f"| {phase} | {len(moves)} | {count} | {100 * count / len(moves) if moves else 0:.1f} |")
    out.append("")

    out.append("## Winning positions\n")
    conv = conversion(games)
    out.append(f"You reached a winning position (winning chances {WINNING:.0f}%+, about a piece up) in "
               f"{conv.reached} games and won {conv.won} ({_pct(conv.won, conv.reached)}).")
    if conv.thrown:
        out.append(f" The {len(conv.thrown)} you didn't win: "
                   + ", ".join(f"[{g.game.id}]({g.game.url})" for g in conv.thrown[:15])
                   + (" ..." if len(conv.thrown) > 15 else ""))
    out.append("")

    out.append("## Openings\n")
    out.append("Your winning chances after move 10, by opening and colour (5+ games), worst first.\n")
    out.append("| Opening | As | Games | Score | Winning chances after move 10 |")
    out.append("|---|---|---:|---:|---:|")
    for row in openings(games):
        out.append(f"| {row.name} | {'White' if row.color == chess.WHITE else 'Black'} | {row.games} "
                   f"| {row.score:.0f}% | {row.win_chance_after_10:.0f}% |")
    out.append("")

    out.append("## By year\n")
    out.append("| Year | Games | Mistakes per game | Missed their threat | Gave them a tactic | Short of time |")
    out.append("|---|---:|---:|---:|---:|---:|")
    years = defaultdict(list)
    for g in games:
        years[g.game.played_at.year].append(g)
    for year in sorted(years):
        group = years[year]
        counts = kind_counts(group)
        out.append(f"| {year} | {len(group)} | {_per(sum(counts.values()), len(group))} "
                   f"| {_per(counts.get(MISSED_THREAT, 0), len(group))} "
                   f"| {_per(counts.get(ALLOWED_TACTIC, 0), len(group))} "
                   f"| {_per(counts.get(LOW_CLOCK, 0), len(group))} |")
    out.append("")

    out.append("## Biggest mistakes\n")
    out.append("| Game | Move | Best | Kind | Winning chances | Clock |")
    out.append("|---|---|---|---|---|---:|")
    worst = sorted(((g, m) for g in games for m in g.mistakes()), key=lambda gm: -gm[1].drop)[:20]
    for g, m in worst:
        clock = "-" if m.seconds_left is None else f"{m.seconds_left:.0f}s"
        out.append(f"| [{g.game.played_at:%Y-%m-%d} {g.game.speed}]({g.game.link(m.ply)}) | {_move_label(m)} "
                   f"| {m.best_san} | {KIND_LABELS[_kind(m)][0]} | {m.before:.0f}% → {m.after:.0f}% | {clock} |")
    out.append("")
    return "\n".join(out)
