# How often the coach says something false

This measures what the README claims: that the coach's checker keeps invented
moves away from the player. It counts how often each model's explanation says
something false about the position, before and after the checker, and what the
checker costs.

Written before any model was run on these positions. A change made because of
what the numbers show gets measured on a fresh set of positions, not this one:
each round has its own positions, answers and labels in `data/round<N>/`.

| Round | Positions (seed) | Models | Checker |
|---|---|---|---|
| 1 | 100 (2026) | `gemma3:12b`, `claude-sonnet` | as first built |
| 2 | 100 (2027) | `claude-sonnet` | after the fixes round 1 prompted (false alarms, line facts) |
| 3 | 100 (2028) | `claude-sonnet`, `claude-opus` | as round 2; the prompt adds what each piece attacks, defends and pins, whose turn it is, and the real move number |
| 4 | 100 (2029) | `claude-sonnet` | as round 3; the prompt adds, for each engine line, what the moved piece does after every move and whether the reply is forced, the full relations of the line's final position, and material and pawn-structure counts; the model then checks its draft against the facts before the checker sees it |

Round 2 runs Claude only: it is now the default, and the local model was
deleted after round 1 to free the disk.

Round 4 changes two things, and keeps them apart: each position's first draft
is recorded as `claude-sonnet-draft` and labelled, blind, alongside the checked
answers. Draft against round 3 measures the new facts; checked answer against
draft, on the same positions and labelled by the same reviewers, measures the
self-check. Only "wrong, no checker" means anything for the draft.

## Steps

1. `python -m evals.positions --round N` plays 50-odd games of the coach's club-strength
   opponent against itself (seeded, searching to depth 8 to save time), takes one position from before move 15
   and one from after in each, always with White to move, as when the player
   asks for an explanation. It stores each position with its engine analysis
   and the exact prompt, so every model explains the same facts. 100
   positions per round, in `data/round<N>/positions.jsonl`, generated once.
2. `python -m evals.collect --round N --model <name>` sends each prompt through
   `verified_completion`, the app's own check-and-retry, and records every
   attempt with the checker's verdict and how long it took.
3. Every attempt is labelled by a reviewer who sees the position, the facts the
   model was given and the answer, but not the checker's verdict and not which
   model wrote it. Answers from all models are shuffled together first.
4. `python -m evals.score --round N` joins labels to answers and writes the round's `results.json`.

Round 1 models: `gemma3:12b` (then the default, local) and `claude-sonnet`
(through a Claude subscription). `qwen3.6:27b` was planned and dropped: it reasons before
answering, took two minutes over a one-sentence reply on an M5 with 32 GB, and
100 explanations would have tied the machine up for about ten hours.

## What counts as a false claim

A statement about this position or this game that the board, the move list or
the engine output contradicts. Opinions are not claims: "a solid position" and
"White should aim for the kingside" are never labelled, however debatable.

| Kind | The answer… | Checker looks for it |
|---|---|---|
| `illegal_move` | names a move that is legal for neither side and is not in an engine line | yes |
| `invented_line` | gives a sequence of moves, as what happens or should happen, that is not a contiguous quote of an engine line (from round 2, or of the game's own moves) | yes |
| `wrong_check` | says a move gives check when it doesn't, or the reverse | yes |
| `wrong_capture` | says a piece is captured or exchanged when it isn't, or the reverse | yes |
| `wrong_attack` | says a move or piece attacks, threatens or defends something it doesn't | yes |
| `wrong_piece` | puts a piece on a square it isn't on, or says a piece is or isn't developed contrary to the position | no |
| `wrong_history` | says a move was played that wasn't, or misstates the game so far | no |
| `wrong_eval` | gets the evaluation wrong: the wrong side better, or a size the scale in the prompt contradicts | no |
| `other` | any other statement the position contradicts (a mate threat that doesn't exist, a wrong count of pawns) | no |

Naming a piece by where it stands ("the Nf3", "supported by Bd3") says where a
piece is, not that a move is played: it is `wrong_piece` only if no such piece
is on that square.

Saying a move is "forced", or that a side "must" play it, is a false claim
(`other`) when other legal moves exist, unless the answer makes clear it means
within the engine line. Round 1's reviewers labelled this; round 2's mostly
let it pass, so from round 3 it is stated.

From round 3, each claim also records `about`: `current` if it is about the
position on the board, `line` if it is about a position inside an engine line
(after one or more of its moves). Round 2's prompt facts covered the current
position far more fully than the positions inside lines.

An answer is **wrong** if it contains at least one false claim. Kinds are
recorded so the checker's blind spots show up, but the headline counts answers.

## What gets reported, per model

- **Wrong, no checker:** answers wrong as first written, out of 100. This is what
  a player would see if the model's text went straight through.
- **Wrong, with checker:** positions where what the player sees is wrong. A
  rejected answer is retried once; if the retry is also rejected the player
  gets an engine-only summary, which can't be wrong about the position.
- **Caught:** of the answers wrong as first written, how many the checker
  rejected; separately, for those with a kind the checker looks for.
- **Fallbacks:** how often the player got the engine-only summary instead of an
  explanation.
- **False alarms:** rejected answers that had nothing false in them.
- **Median seconds** per answer.
