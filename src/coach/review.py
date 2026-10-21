"""The model's second pass over its own draft, checking it against the facts.

Round 3 showed that adding facts to the brief had stopped helping: about a
quarter of answers still said something false. Checking a statement against a
list is an easier job than writing correctly from scratch, and in round 4
handing the draft back with the facts cut false answers from 24 in 100 to 6.

Two ways to ask for it. `rewrite` has the model write the whole corrected
answer, which is what round 4 measured. `edit` numbers the draft's sentences and
asks only for the ones to change: writing out the whole answer again is most of
the check's time. In round 5, on the same positions, `edit` left 5 false answers
in 100 against `rewrite`'s 3 - no detectable difference - and took 14 seconds
an answer against 17, so it is the default.

Round 6 also had the model list its claims in a fixed form for the board to
decide. It changed nothing (7 false answers in 300 before and after): the
model listed the claims it believed, so the false ones were never on the list.
That check was removed; it is in git history.
"""

import json
import re
from typing import Callable, Dict, List

from src.coach import claude_cli

CHECKLIST = """Check every statement in the draft about the position, the game or the engine
lines against the facts in the brief:
- a piece attacking, defending, protecting, supporting or pinning something:
  PIECE RELATIONS for the current position; MOVE BY MOVE and POSITION AT THE
  END OF THIS LINE for positions inside an engine line
- which piece makes a move, and which pieces are developed: MOVE BY MOVE (it
  names the square each piece came from) and DEVELOPMENT
- material, doubled, isolated or passed pawns, open files: MATERIAL AND PAWNS,
  or a line's end-position facts
- a move being forced, or a side having to play it: only if MOVE BY MOVE says
  that reply is forced
- checks, captures, trades and material over a line: that line's FACTS
- a side being better in a positional factor, or a line improving one:
  POSITIONAL FACTORS and the line's POSITIONAL CHANGE; where its
  WHAT THE FACTORS SHOW says they do not explain the line, any reason the
  draft gives for it is unsupported - replace it with the plain statement that the engine
  prefers the line for reasons these factors do not show
- how big an advantage is: the words given beside each evaluation
- move sequences: only the ENGINE LINES, quoted exactly, or the moves played"""


class ReviewError(Exception):
    """The check's reply could not be applied to the draft."""


def _brief_and_draft(brief: str, draft: str) -> str:
    return f"""You are checking a chess explanation for false statements before a student reads it.

THE BRIEF the explanation was written from, with every verified fact about the position:
<<<
{brief}
>>>

THE DRAFT:
<<<
{draft}
>>>

{CHECKLIST}"""


def rewrite_prompt(brief: str, draft: str) -> str:
    return f"""{_brief_and_draft(brief, draft)}

Delete or correct every statement the facts do not support. Keep everything
else as it is, including opinions and plans, and keep the same tone and length.

Reply with the corrected explanation only - no preamble and no list of changes.
"""


# A sentence ends at . ! or ? followed by a space, except after a digit or
# another dot, so "15. e4" and "15... Nf5" stay inside their sentence. Every
# line break also ends one, so list items and headings stand alone.
_BOUNDARY = re.compile(r"(?<=[^\d.][.!?])[ \t]+|[ \t]*\n\s*")


def sentences(text: str) -> List[str]:
    """The text cut into sentences, each keeping the whitespace after it, so
    that joining them gives back the text exactly."""
    pieces, start = [], 0
    for match in _BOUNDARY.finditer(text):
        if match.start() > start or not pieces:
            pieces.append(text[start:match.end()])
        else:
            pieces[-1] += text[start:match.end()]
        start = match.end()
    if start < len(text):
        pieces.append(text[start:])
    return pieces


def edit_prompt(brief: str, pieces: List[str]) -> str:
    numbered = "\n".join(f"[{n}] {piece.strip()}" for n, piece in enumerate(pieces, 1))
    return f"""{_brief_and_draft(brief, numbered)}

The draft's sentences are numbered. Correct or delete every sentence the facts
do not support; leave everything else, including opinions and plans, alone.

Reply with a JSON object only, mapping the number of each sentence to change to
its full corrected text exactly as it should appear (keep any list marker or
bold), or to "" to delete it. Reply {{}} if nothing needs changing.
"""


def _object(reply: str) -> Dict:
    start, end = reply.find("{"), reply.rfind("}")
    try:
        parsed = json.loads(reply[start:end + 1]) if start != -1 else None
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        raise ReviewError(f"not a JSON object: {reply[:80]!r}")
    return parsed


def _corrected(pieces: List[str], corrections: Dict) -> List[str]:
    pieces = list(pieces)
    for key, text in corrections.items():
        if not (str(key).isdigit() and 1 <= int(key) <= len(pieces)) or not isinstance(text, str):
            raise ReviewError(f"no sentence {key!r} to replace with {text!r}")
        piece = pieces[int(key) - 1]
        pieces[int(key) - 1] = text + piece[len(piece.rstrip()):] if text else ""
    return pieces


def board_prompt(brief: str, pieces: List[str], fen: str) -> str:
    """The edit check, done with the board tool to hand instead of from the brief.

    The reviewers who caught round 6's last errors did not read the brief more
    carefully: they asked a board about each statement. This asks the model to
    do the same.
    """
    numbered = "\n".join(f"[{n}] {piece.strip()}" for n, piece in enumerate(pieces, 1))
    return f"""You are checking a chess explanation for false statements before a student reads it.

THE BRIEF the explanation was written from (the engine's evaluation and lines,
and facts about the position):
<<<
{brief}
>>>

THE EXPLANATION, sentence by sentence:
<<<
{numbered}
>>>

You have a board tool. The position on the board now is:
FEN: {fen}
A position inside an engine line is that FEN with the line's moves, in SAN and
without move numbers, played up to the point the sentence is about. To ask
whether something depends on a piece, call the tool with that square in
"without".

The brief's facts are not enough on their own: earlier checks that read only
the brief let through a king put on the wrong square, a pawn called passed
with an enemy pawn in front of it, and a pin said to be broken that still held.
So you must use the board tool. First call it on the current position. Then go
through the explanation one sentence at a time, and for every sentence that
says something about a position - where a piece stands, what a piece or a move
attacks, defends, pins or unpins, whether a pawn is passed, doubled or
isolated, material, development, which moves are legal, whether a reply is
forced, check, mate, what is captured or traded in a line - call the tool on
the position that sentence is about (for a line, with its moves played up to
that point) and check the sentence against what the tool returns. Evaluations,
engine lines and opinions are judged against the brief.

Correct or delete every sentence the board or the brief contradicts; leave
everything else alone.

Your final reply must be a JSON object only, mapping the number of each
sentence to change to its full corrected text exactly as it should appear
(keep any list marker or bold), or to "" to delete it. Reply {{}} if nothing
needs changing.
"""


def apply(pieces: List[str], reply: str) -> str:
    """The draft with the numbered corrections in `reply` made."""
    return "".join(_corrected(pieces, _object(reply)))


def rewrite(llm, brief: str, draft: str) -> str:
    return llm.generate_content(rewrite_prompt(brief, draft)).text


def edit(llm, brief: str, draft: str) -> str:
    pieces = sentences(draft)
    return apply(pieces, llm.generate_content(edit_prompt(brief, pieces)).text)


def board(model: str, brief: str, draft: str, fen: str, generate: Callable = claude_cli.generate_with_board) -> str:
    """A last pass over checked text with the board tool to hand (Claude only).

    Piloted on round 6's shown answers: it fixed 4 of the 7 that reviewers had
    found false and changed none of 43 correct ones for the worse, for about 9
    seconds more an answer.
    """
    pieces = sentences(draft)
    return apply(pieces, generate(model, board_prompt(brief, pieces, fen)))
