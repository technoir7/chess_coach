# Card commentary: how often it says something false, and whether it teaches

The flashcards made from a player's games (`make_cards.py`) give the line,
what it wins, what was played and what was better. Commentary adds two or
three sentences on why: what the threat attacks, what the mistake left
undefended, what the winning move exploits. It also adds one line on a habit
to take into games.

The coach's general explanation of a position was tried first and left out:
on 2 of 2 cards about a threat it said there was no threat, because it
doesn't know what the card is teaching and its threats are only pieces
hanging now. Commentary gets a brief built for the card instead: the card's
question and answer, the position's facts, each of the card's lines played
out move by move, and what the move played changed (pieces it left
undefended or newly attacked, pieces it stopped defending). The draft is
then checked the way the coach's explanations are: against the brief, then
with a board tool to hand, then by the move verifier.

Written before any commentary was generated.

## Method

Each round takes cards no earlier round used, drawn at random (seeded) from
one player's deck. Each card's first draft and its checked commentary are
both kept. Reviewers see them shuffled together, with no hint of which is
which. For each one they get the card's position, question and answer, and
the commentary. Identical texts are labelled once.

Reviewers check every statement in the commentary against the board with
python-chess, and the engine lines against the card. They record:

- **False claims**: any statement the board or the card contradicts, quoted,
  with why. A commentary is wrong if it has at least one.
- **Teaches**: does it explain why the card's answer is right, in terms a
  club player could reuse? `yes`, `partly` (true but generic, or misses the
  main point), or `no`.
- **Lesson fits**: is the "Lesson:" line a habit that would have caught
  this mistake? `yes` or `no`.

Only each round's counts (`results.json`) are kept in
`evals/data/cards-round<N>/`. The cards, commentary and labels come from one
player's own games, so they stay on that player's machine.

## What counts as good enough

Round 1 has 40 cards. The coach's own explanations ended at 1 to 4 false in
100 (README, rounds 9 to 12). Commentary is shorter, so the bar is the same
or better:

- **Ship** it for the whole deck if at most 1 of 40 checked commentaries is
  wrong, and at least 30 of 40 teach (`yes`).
- **Otherwise** fix what the reviewers found and run a new round on fresh
  cards. Don't rerun the same cards: fixes tuned to them would flatter the
  count.

Draft against checked, on the same cards and reviewers, measures what the
checks add, as round 4 did for the coach.

## Round 1

40 cards (23 "what does it allow", 9 "find the best move", 8 "what is the
threat"), labelled blind by 3 reviewers; drafts and checked commentary
shuffled together, 61 distinct texts.

| | Draft | Checked |
|---|---:|---:|
| Wrong | 12 of 40 | 2 of 40 |
| Teaches: yes / partly / no | 24 / 16 / 0 | 27 / 13 / 0 |
| Lesson fits | 40 | 39 |

The checks changed 21 drafts and cut false commentary from 12 to 2. Median
24 seconds a card. Neither bar is met (at most 1 wrong, at least 30 teach),
so round 2 runs on fresh cards with these fixes:

- **"The queen gone for just a rook"** (c11, and a draft of another card):
  the brief listed each capture and the model netted them wrongly; the
  rooks were traded and the queen lost for nothing. Each line now states
  the pieces each side loses, with even trades cancelled.
- **"Your bishop on c8 and pawn on f7 have nowhere to go"** (c32, and two
  drafts): the brief's list of where an attacked piece can go said
  "nowhere" for pieces that couldn't move only because their king was in
  check. In check, the list is no longer given.
- **Teaches "partly"** was mostly the main mechanism left unnamed: a
  discovered check (c13, c40), a pin (c19), a fork further down the line
  (c22, c36). The brief left these for the model to spot. Each line now
  lists its tactical events read off the board - discovered and double
  checks, pins a move creates, double attacks by the moved piece - and the
  instructions ask for the idea to be named.

## Round 2

40 fresh cards, the fixes above, 3 new reviewers, 58 distinct texts.

| | Draft | Checked |
|---|---:|---:|
| Wrong | 9 of 40 | 2 of 40 |
| Teaches: yes / partly / no | 26 / 14 / 0 | 27 / 13 / 0 |
| Lesson fits | 39 | 39 |

The same as round 1 on both bars. One reviewer was much stricter on
"teaches" than the others (7 of 18 yes, against 15 of 20 and 14 of 20).
The two false commentaries both claimed more than the brief's facts:

- **"Its only safe retreat is g6"** (c15): the brief called a square no
  enemy piece attacks "safe"; the bishop was trapped there by h5 two moves
  later. The brief now says "not attacked there".
- **"Qc3 defends the c4 pawn, leaving nothing to grab"** (c22): it does
  defend it, but taking it still wins for Black. The instructions now say
  never to claim the opponent can't do something unless a fact says so.

The "partly" notes mostly named a deciding reason left out: a defender
guarding two attacked pieces (c40), a pinned pawn that can't recapture
(c26), a rook lured away (c29), or a better move said to "defend" without
how it stops the tactic (c07, c16, c20). The brief now states overloaded
defenders (a piece that is the only defender of two attacked pieces), in
the card's position and after each line's attacking move, and what the
better move does: what its piece attacks and defends, and whether the
opponent's threat or reply is still a legal move after it. The
instructions ask for the deciding reason by name.

## Round 3

40 fresh cards, the fixes above, 3 new reviewers, 57 distinct texts.

| | Draft | Checked | Checked, second reviewers |
|---|---:|---:|---:|
| Wrong | 6 of 40 | 1 of 40 | 2 of 40 |
| Teaches: yes / partly / no | 28 / 12 / 0 | 31 / 9 / 0 | 35 / 5 / 0 |
| Lesson fits | 38 | 38 | 39 |

Both bars are met, so commentary is turned on for the whole deck. Two new
reviewers labelled the 40 checked commentaries again, independently and
reshuffled: 2 wrong and 35 teaching, so the result doesn't hang on who
labelled it.

Both sets of reviewers found the same false commentary: "your Knight on b4
and Bishop on f5", Black's pieces on a card for White. Two drafts this
round and one in round 1 did the same, and the checks let one through. A
last check now rejects "your <piece> on <square>" where the player never
has that piece there, in the card's position or any of its lines; the
commentary is then written again. Over all 240 texts of rounds 1 to 3 it
flags exactly those 4 and nothing else. It is not yet measured on fresh
cards; it can only reject.

The second reviewers' other false claim is borderline: "the Knight on c3
and Rook on e3 both cover e4" of a knight pinned to its king, which can't
recapture there.

## After round 3: the commentary's line matches the card's

Cards now cut their line once the material is won, so a hung rook shows
its capture, not the trades after it. Commentary was still written from
the engine's longer line, and on a hung rook narrated "after 23. a3
Rxd1+ ... after 24. Qxd1" as if it were a combination. The brief's line
with the tactic now stops where the card's does, and the move check
rejects anything quoted past it. Of the 547 commentaries written for the
deck, 28 went past their card's line and were written again. Like the
ownership check, this is not measured on fresh cards; it can only reject.
