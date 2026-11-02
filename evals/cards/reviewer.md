# Instructions for reviewers of card commentary

You are labelling commentary written for the back of chess flashcards. Each
card comes from a mistake in a club player's own game. Your batch is a JSON
list; each item has:

- `player`: the side the card is for (it is that side's move in `fen`)
- `fen`: the card's position
- `threat_fen`: when present, the same position with the other side to move;
  the card's threat line starts from it
- `question` and `answer`: the front and back of the card, already verified
- `brief`: the facts and engine lines the writer was given
- `commentary`: what you are labelling

## False claims

Check every statement in the commentary against the board. Use python-chess
(run `env/bin/python` from the repository root; `import chess`) rather than
reading the position by eye: set up the FEN, play a line's moves, and look at
what is attacked, defended, pinned, where a piece can go, what is captured,
whether a move is legal or gives check. A statement about a line is judged on
the line as the brief gives it. Judgements ("better", "strong", "winning")
are judged against the brief: the answer's winning chances and the engine
lines.

The "Lesson:" line is advice. It is false only if it states a fact about
this position that the board contradicts.

Record a claim as false when the board or the brief contradicts it. Do not
record style, vagueness, or something left out. If a natural reading of the
sentence is true, it is not false; if most players would read it in a way
that is false, it is.

## Teaches

- `yes`: it explains why the card's answer is right in chess terms a player
  could reuse - names what is undefended, trapped, overloaded, forked or
  pinned, the line or square that matters, and why the better move solves it.
- `partly`: true, but generic, or it misses the main point.
- `no`: it only restates the answer, or doesn't say why.

## Lesson fits

`yes` if the "Lesson:" line is a habit that would plausibly have caught this
mistake during the game; `no` if it wouldn't, or there is no lesson.

## Output

Write one JSON object per line to the labels file you were given, one for
every item in your batch, in any order:

```json
{"key": "...", "claims": [{"quote": "...", "why": "..."}], "teaches": "yes", "lesson_fits": "yes", "note": "one short sentence"}
```

`claims` is `[]` when nothing is false. Label every item; change no other file.
