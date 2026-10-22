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
| 5 | 100 (2030) | `claude-sonnet-rewrite`, `claude-sonnet-edit` | as round 4; the prompt adds each evaluation's band in words, whose piece each capture takes, the material after a line's cheapest recapture, where each line move's piece came from, and which minor pieces are still at home |
| 6 | 300 (2031) | `claude-sonnet-claims` | as round 5, with the pin note reworded ("it may only move along that line"); the self-check also lists the answer's claims in a fixed form, the board decides each, and a sentence the board contradicts is rewritten with the truth or deleted |
| 7 | 100 (2032) | `claude-sonnet-edit-board` | as the app after round 6: the edit self-check, then the board pass; the verifier's prose checks removed; the prompt adds Stockfish 16's positional factors, marks each line tactical or positional, and asks for tactics and position in separate parts |
| 8 | 100 (2033) | `claude-sonnet-edit-board` | as round 7, with the fixes its reviewers prompted; the prompt adds why the engine ranks a quiet first choice above its other lines, candidate passed pawns, and material in points |
| 9 | 100 (2034) | `claude-sonnet-edit-board` | as round 8, with the fixes its reviewers prompted; each line runs on while the engine keeps capturing or checking, and the played-out exchange and the checker's allowance for recaptures are gone |
| 10 | 100 (2035) | `claude-sonnet-edit-board`, `claude-sonnet-edit-board-round9-instructions` | as round 9, with the fixes its reviewers prompted; the new arm is asked to open with the verdict, explain in chess terms rather than factor scores, join tactics and position where they are one idea, and end with what to aim for; the other arm answers the same prompts with round 9's instructions |
| 11 | 100 (2036) | `claude-sonnet-edit-board` | as round 10's new arm, with the fixes its reviewers prompted: a worse move's own line not offered as why it is worse, no warning against a move about as good, the material note when the evaluation barely favours the side ahead |
| 12 | 100 (2037) | `claude-sonnet-edit-board` | as round 11, with facts for the general chess remarks its answers got wrong: threats to each side, outposts, what stands in the way of castling, knights on the edge |

Round 2 runs Claude only: it is now the default, and the local model was
deleted after round 1 to free the disk.

Round 4 changes two things, and keeps them apart: each position's first draft
is recorded as `claude-sonnet-draft` and labelled, blind, alongside the checked
answers. Draft against round 3 measures the new facts; checked answer against
draft, on the same positions and labelled by the same reviewers, measures the
self-check. Only "wrong, no checker" means anything for the draft.

Round 5 runs two versions of the self-check on the same positions:
`rewrite` (round 4's: the model writes the whole answer again) and `edit` (the
draft's sentences are numbered and the model returns only the ones it changes).
Only the checked answers are labelled. The question for `edit` is whether it
is as accurate as `rewrite` and faster; the comparison with round 4 is across
different positions and reviewers, so only a large change in it means much.

Round 5's first run was stopped after three positions and discarded, unlabelled:
the checker rejected answers that repeated the new recapture fact ("if White
takes back with fxe3") because the recapture is in no engine line. The checker
now accepts it, and the run started again from the first position.

Round 6 is three times the size: at 3 to 5 false answers in 100, a round of
100 cannot tell 4 from 2. It runs one arm, `claims`, and also records each
first answer as the model's own check left it, before the board checked its
claims (`claude-sonnet-claims-firstpass`). Both are labelled, shuffled
together; an answer the board's check did not change is the same text in both
and is labelled once. Final against first pass, same positions and reviewers,
measures what checking claims on the board adds.

Result: 7 of 300 wrong both before and after the board checked the claims;
the board changed 3 answers, none of them among the 7. The claim check was
removed (it is in git history at a2b1726), and so were the verifier's checks
on prose about checks, attacks and trades, which rejected 20 correct answers
over rounds 4 to 6 and caught no wrong one. Re-run over those rounds' 1,014
answers, the remaining checker rejected 2, both false alarms (one side's moves listed without the other's), and now accepts those.

Labelling round 6 took 11 reviewers at roughly 200,000 tokens each; the
answers themselves took about 900 Claude calls.

Changed after round 6 and not yet measured, all from what its reviewers
found in the prompts: the endgame is decided by the material left rather than
the move count (a full board had been called an endgame at move 22); a piece
pinned to its king is given its remaining legal moves rather than a rule about
them (a pinned knight "may only move along that line" when it cannot move at
all); and a line in which both queens are taken says the queens are traded.

Also unmeasured: the prompt now carries Stockfish 16's positional factors,
marks each line tactical or positional, and asks for the explanation in two
parts, tactics and position. The rounds above measured false claims, mostly
tactical ones; positional claims ("White's mobility is better") are new, and
need labelling against the factor table as well as the board.

Round 7 measures the app as it now runs, on fresh positions: the first
round with the board pass in the app and with positional factors in the
prompt. Its reviewers also record, for each answer, whether it keeps tactics
and position apart as asked (`separation`); that is not a false claim and is
reported on its own.

Result: 6 of 100 answers wrong, none caught or rejected by the verifier, at a
median of 22 seconds. One of the 6 is positional: "Bxf6 wrecks Black's
structure", where the line's positional change shows none. The rest are
slips about the position (a side's options credited to the other, the king's
legal moves counted with a block among them, "material level" where the line
leaves it 5 pawns apart, a defended pawn called loose). Round 6's 7 of 300
had different reviewers; 6 in 100 is in line with rounds 4 and 5, so the
change cannot be told from noise. 88 answers kept tactics and position apart;
the 12 that did not walked through a positional line in the Tactics part
(`separation.json`).

The reviewers found these in the prompts, fixed after round 7 and not yet
measured: Stockfish 16 skips most factors when one side is far ahead in
material, and the prompt showed the zeros as "about even"; a factor could
favour a side with no piece of that kind, through the other side's penalty,
with no sign of it; "tactical (the line wins material)" did not say who
wins it; and a piece shielding a defended piece worth no more than its
attacker was called pinned.
The prompt also now says each engine line goes in the part its KIND names,
for the 12 answers that mixed them.

Also changed after round 7, and not yet measured. A quiet first choice now
comes with why the engine ranks it above each of its other lines. The first
version asked whether the line improved Stockfish 16's factors on the
position now; of round 7's 51 quiet first choices it explained 17, and p001
shows what filled the gap - White gets "a centralised knight on d4" for a
line whose factors moved towards Black. That was the wrong question: an
engine compares its moves with each other, and often every move gives a
little ground. Over rounds 6 and 7 (400 positions, 203 quiet first choices),
comparing the moves instead: in 77 every other line is within 20cp, about as
good (p001's d4 and Be2 are 2cp apart); in 60 each worse line loses material
or ends with factors worse for the side to move; in 48 the only gaps the
factors do not explain are under 50cp, called small; in 18 (9%) a gap of 50cp
or more is unexplained, and the answer is told to say so. Two other routes
did not help. Classical Stockfish 16, searching on the same factors, chose
moves that its own factors at the end of its lines explained no more often
(11 of 51). Turning each of its terms off in turn to see which one decides
the choice gave results swamped by search noise (one "drop" of 27 pawns in a
1.6-pawn preference). A line heading for a forced mate beyond its eight moves
is now tactical; it had been called quiet.
Pawn structure now lists candidate passed pawns by Stockfish
16's rule. Over every round's positions and line ends (3,572 boards), a side
has a passed or candidate passed pawn in the list exactly when Stockfish 16
scores one; 80 of the 1,800 sides had a candidate and no passed pawn, which
is where "passed pawns favour White" sat beside "White passed pawns: none".
Material is counted in points rather than "pawns": "6 pawns ahead" was
repeated for a side a bishop and a knight up.

Round 8 measures those changes on fresh positions, run as round 7 was.
Besides false claims, its reviewers record for each answer whose prompt gives
WHY THE ENGINE RANKS IT FIRST whether the answer follows it (`why_first`):
`follows` if every reason it gives for the first choice over another line is
one the prompt gives, it calls no "about as good" line better or worse, and
where the prompt says the factors do not show the reason it says so;
`invents` if it gives a reason the prompt does not, or ranks moves the prompt
calls about as good; `silent` if it does not say why the first choice is
preferred. Before the change, round 7's p001 would be `invents`. The question
is how many are `invents`; `silent` is reported, not counted as wrong.

Result: 3 of 100 answers wrong, none caught or rejected by the verifier, at a
median of 30 seconds (round 7: 6 of 100; at this size the two cannot be told
apart). One is positional: p094 gives Qc3 "mobility 0.40 better than the Qb4
line", where the prompt's 0.40 is against Qc4. One repeats a fact the prompt
got wrong: p095's exchange "played out" leaves White a point up, but the
knight on d4 is then loose and Black takes it. One is a slip about the
evaluation. 99 answers kept tactics and position apart. Of the 47 answers
given WHY THE ENGINE RANKS IT FIRST, 41 follow it, 2 are silent and 4 invent
(`why_first.json`): two (p019, p094) give a factor comparison made against one
line as if it were against another, since the prompt said "where the lines
end, e4's has…" without naming the other line; one ranks a move called about
as good below others (p073); one calls a line about as good "not a safe way
out" before saying all three are about as good (p046).

Fixed after round 8, not yet measured: the comparison names the other line
("compared with g3's line, e4's ends with…"); and material lost is given as
why a line is worse only when the gap is at least 50cp per point, since p092's
"its line loses 1 point" sat on a 24cp gap, beside a line also a point down
and about as good. Also fixed, not yet measured: a line stopping mid-exchange was played out
by taking on that square only, which missed a piece left loose elsewhere, as
in p095. A capture-only search over the whole board was no answer: on 160
line ends where it changed the count, it was further from Stockfish's
evaluation than the old count 54 times, misled by checks that come first and
quiet moves that defend. Each line now runs past its 8 moves while the
engine's own line keeps capturing or checking, up to 20, and the engine is
searched again where its line runs out first. Over round 8's positions, 94
of the 300 lines run on (40 needing another search), and the facts take 0.45
seconds at the median. The played-out exchange is gone, and with it the
checker's allowance for naming a recapture no line plays.

Round 9 measures those fixes on fresh positions, run and labelled as round
8 was, `why_first` included. Because the checker no longer accepts a
recapture that no line plays, it also reports how many answers the checker
rejected and whether those rejections were false alarms.

Result: 2 of 100 answers wrong, at a median of 28 seconds (round 8: 3, round
7: 6; at this size not a clear change). One is positional: p096 puts a pawn
structure gap down to White's isolated f- and h-pawns, where Black's are
isolated the same way. One repeats a line's material count where the
engine's next move takes a piece back (p014). The checker rejected one
answer, a false alarm: "the Rf8" named a rook that reaches f8 by castling in
the line, where only the current board was checked; it now checks the
positions inside each line too. 98 answers kept tactics and position apart.
Of 49 answers given WHY THE ENGINE RANKS IT FIRST, 47 follow it and 2 invent:
one warns off a line called about as good (p091, like round 8's p046), one
calls all three moves about as good where two were slightly worse (p059).

The reviewers found three lines whose material count the engine does not
bear out: a line ends on a quiet move after which the engine takes a piece
(p014), forks queen and rook (p095, "White wins 3 points" at -262), or wins
a pawn back (p081). A line stops at the engine's first quiet move, which is
not where its sight ends. Running each line on until four moves pass with no
capture or check, with a fresh search from move 8, did worse: where it
changed the count, the engine's evaluation sided with it 26 times and with
the lines as they are 45 times, and 47 of 289 lines ran to the 20-move cap.
Instead, a line whose count leaves one side ahead, where the engine's
evaluation of the line does not favour that side, now says so, and that the
side ahead is not to be called the one who keeps it (26 of round 9's 298
lines). Not yet measured.

Round 10 asks whether the answers can be made more useful without making
them less accurate. The player asked for what is most useful rather than a
strict split into tactics and position, and round 9's answers were accurate
but read as reports on the brief: every line walked through, factor scores to
two decimals, the brief's labels named, no takeaway. The new instructions
change only the text after the grounding rules; the comparison arm answers
the same prompts with round 9's text (`evals/round9_instructions.txt`,
`collect --instructions`). Both arms' answers are labelled for false claims,
shuffled together as before, with `why_first`; `separation` is no longer
asked for. Separately, judges see each position's two answers in random order
(`python -m evals.pairs`) and pick the one more useful to a player who wants
to understand the position and play it better, or `same`, judging only what
is true by the facts. The questions: does the new arm win more pairs than it
loses, and is it wrong no more often?

Result: the judges preferred the new arm in 97 of 100 pairs (`pairs.json`):
the old arm's answers read as reports, factor scores and every line in turn,
with no plan; the new arm's explained the idea in pieces and squares and said
what to aim for. The new arm was also wrong less often, 1 of 100 against 3
(both at a median of 27 seconds, 242 words against 287; the checker rejected
none). But it invented a reason for the engine's ranking in 10 of 66 answers
against 1 (`why_first.json`): asked what goes wrong with another move, it
offered a true feature of that move's line ("Why not exd5? White ends up with
an isolated pawn") as the reason, where the brief gives another; and it warned
against moves called about as good ("be careful with that one"). It also kept
closing with how a club player would see the position, which a grounding rule
told it to describe whenever it mentioned it.

Fixed after round 10, not yet measured: the instructions say a worse move is
worse for the reason the brief gives, and what its line does is not to be
offered as that reason; a move about as good is not to be warned against,
including in what to aim for; and the human-intuition reading is described
that way only if mentioned. The material note now also fires when the
engine's evaluation barely favours the side ahead (p051: Black 3 points up at
-10cp, the pinned bishop won back next move): below half a pawn a point, up
to a clear advantage (100cp), since evaluations do not grow with material.
It fires on 87 of rounds 9 and 10's 595 lines.

Round 11 measures those fixes on fresh positions, one arm, labelled as round
10 was. The question is whether `invents` falls back from round 10's 10 in
66 towards rounds 8 and 9 (4 in 47, 2 in 49) while false claims stay low.
Usefulness is not judged again: the instructions changed in two sentences.

Result: `invents` fell to 2 of 56 (round 10: 10 of 66), both a worse move's
own line changes read as the reason (`why_first.json`). 4 of 100 answers were
wrong, at a median of 24 seconds and 242 words, none rejected: a knight on g4
said to be on the edge (p037), an "outpost" on e5 that f7-f6 attacks (p095),
"no immediate threat" where a pawn attacks a knight (p015), and Nf3 said to
prepare queenside castling, already legal (p085). All four are the
general chess remarks the new instructions ask for, not the engine facts
earlier rounds got wrong; at 1 in round 10's arm and 4 here, 100 answers
cannot say whether the style costs accuracy. The human-intuition reading
closed 18 answers, against most of round 10's.

Fixed after round 11, not yet measured: the brief now states what those four
remarks needed. THREATS lists, for each side, every piece attacked and
undefended or attacked by something cheaper, with its attacker (the board
already worked these out for the in-game advice, but never showed them to the
explanation). MATERIAL AND PAWNS lists outposts: squares on a side's fourth to
sixth ranks that its pawn defends and no enemy pawn can ever attack.
DEVELOPMENT says, for each castling, whether it is legal now, what stands in
the way, or that the right is gone, and names any knight on the edge of the
board. A grounding rule and the check's checklist bind those remarks to them.
Threats are listed in 44 of round 11's 100 positions.

Round 12 measures this on fresh positions, one arm, labelled as round 11 was.
The question is whether false claims fall back from round 11's 4 towards
round 10's 1, with no new kind of mistake about threats, outposts or castling,
and `invents` stays near round 11's 2 in 56.

Result: 1 of 100 answers was wrong (round 11: 4), at a median of 23 seconds
and 242 words, none rejected. The one mistake is of an older kind: "White gets
enough for the pawn it gives up" in a line where White takes the pawn straight
back (p002). The answers now use the new facts far more: outposts come up in
27 answers (round 11: 1), threats in 62 (13), castling in 31 (27), and the
reviewers, who checked the new facts against the board, found none of them
wrong and no false claim about any of them. `invents` was 2 of 53 (round 11:
2 of 56), both a worse or equal move's own line given as a drawback (p011,
p060). The human-intuition reading closed 15 answers.

## Board-check pilot

`python -m evals.board_pilot` gives the model's check a tool that describes
any position and runs it as a last pass over round 6's shown answers: the 7
reviewers had found false and a seeded 43 of the correct ones. Only the
answers it changed (14) were labelled, blind, by one reviewer; the rest keep
their round 6 labels. It fixed 4 of the 7 and made none of the 43 worse. One
changed answer was labelled false for a sentence it had kept unchanged from
round 6 ("if White recaptures with Qxd4 it comes out 3 pawns ahead", where
Bxd4 then wins the queen) - a fact the prompt itself had stated. The facts now
play out the whole exchange where a line stops.

In the first try the model called the tool in none of 6 checks, answering from
the brief instead; those were discarded, and the prompt now says the brief's
facts are not enough and the tool must be used.

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
| `wrong_positional` | from round 7: says a side is better or worse in a positional factor, or that a line improves or worsens one, contrary to POSITIONAL FACTORS or a line's POSITIONAL CHANGE; or gives a concrete positional reason the board contradicts (an "outpost" an enemy pawn can attack, a "bad bishop" with no own pawns on its colour, an "open file" with pawns on it) | no |
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
