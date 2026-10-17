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
"""

import json
import re
from typing import Dict, List, Sequence

import chess

from src.coach import claims as board_claims

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


def apply(pieces: List[str], reply: str) -> str:
    """The draft with the numbered corrections in `reply` made."""
    return "".join(_corrected(pieces, _object(reply)))


# The board and the engine lines are only used by `claims`; the other checks
# take them so that every check can be called the same way.

def rewrite(llm, brief: str, draft: str, board: chess.Board, lines) -> str:
    return llm.generate_content(rewrite_prompt(brief, draft)).text


def edit(llm, brief: str, draft: str, board: chess.Board, lines) -> str:
    pieces = sentences(draft)
    return apply(pieces, llm.generate_content(edit_prompt(brief, pieces)).text)


CLAIM_KINDS = """- attacks {"piece": "f3", "target": "e5"}: the piece on f3 attacks the enemy piece (or empty square) e5
- defends {"piece": "d1", "target": "d4"}: the piece on d1 defends its own piece on d4
- defended {"square": "a3"}: some piece defends the piece on a3 (record "loose",
  "hanging", "undefended" or "unprotected" as this with "holds": false)
- pinned {"square": "f6"}: the piece on f6 is pinned
- can_move {"square": "e4"}: the piece on e4 has at least one legal move
- forced {}: the side to move has only one legal move ("must", "has to", "forced")
- check {"move": "Bb5+"}: that move, played from this position, gives check
- connected_rooks {"side": "White"}: nothing stands between that side's two rooks
- all_minor_pieces_developed {"side": "White"}: no knight or bishop of that side
  is still on its starting square ("completes development", "the last minor piece")
- piece_on {"square": "c1", "piece": "knight", "side": "White"}
- material {"leader": "White" | "Black" | "level"}
- pawn {"square": "c6", "kind": "doubled" | "isolated" | "passed"}
- open_file {"file": "d"}: no pawns on that file"""

CLAIM_FORMAT = """Each claim is {"sentence": <number>, "at": <position>, "kind": <kind>, "args": {...}, "holds": true or false}.
<position> is "current" for the position on the board now, or {"line": "<the
first move of the engine line>", "after": "<the move, as numbered in that
line, just after which the claim is about>"}, e.g. {"line": "Nf3", "after":
"16... Rc8"}. Squares are where the pieces stand in that position. "holds":
false records a denial, such as "the rooks are not connected" or "the pawn
cannot move"."""


def claims_prompt(brief: str, pieces: List[str]) -> str:
    numbered = "\n".join(f"[{n}] {piece.strip()}" for n, piece in enumerate(pieces, 1))
    return f"""{_brief_and_draft(brief, numbered)}

The draft's sentences are numbered. Do two things.

1. Correct or delete every sentence the facts do not support; leave everything
   else, including opinions and plans, alone.
2. List every claim of the kinds below that the sentences make, as they read
   after your corrections, so that a program can check each one against the
   board. Leave out claims of any other kind.

{CLAIM_KINDS}

{CLAIM_FORMAT}

Reply with a JSON object only: {{"corrections": {{"<number>": "<the full corrected
sentence exactly as it should appear, keeping any list marker or bold>" or ""
to delete it}}, "claims": [...]}}.
"""


def fix_prompt(brief: str, pieces: List[str], findings: List[board_claims.Finding]) -> str:
    numbered = "\n".join(f"[{n}] {piece.strip()}" for n, piece in enumerate(pieces, 1) if piece.strip())
    wrong = "\n".join(f"- sentence {f.sentence}: {f.truth}" for f in findings)
    return f"""You are correcting a chess explanation before a student reads it.

THE BRIEF it was written from:
<<<
{brief}
>>>

THE EXPLANATION, sentence by sentence:
<<<
{numbered}
>>>

A program checked the explanation's claims against the board, and these
sentences claim something the board contradicts:
{wrong}

Rewrite each of those sentences so that everything it says is true, or delete
it. Leave every other sentence alone. Then list the claims your rewritten
sentences make, in the same form as before:

{CLAIM_KINDS}

{CLAIM_FORMAT}

Reply with a JSON object only: {{"corrections": {{"<number>": "<the full
rewritten sentence>" or ""}}, "claims": [...]}}.
"""


def _claims_reply(reply: str):
    parsed = _object(reply)
    if not isinstance(parsed.get("corrections", {}), dict) or not isinstance(parsed.get("claims"), list):
        raise ReviewError(f"no corrections and claims in {reply[:80]!r}")
    return parsed.get("corrections", {}), parsed["claims"]


def first_pass(draft: str, reply: str) -> str:
    """The draft with only the model's own corrections from a `claims` reply made."""
    corrections, _ = _claims_reply(reply)
    return "".join(_corrected(sentences(draft), corrections))


def claims(llm, brief: str, draft: str, board: chess.Board, lines: Sequence[Sequence[str]]) -> str:
    """The edit check, plus a list of claims that the board then decides.

    A sentence whose claim the board contradicts goes back to the model with
    the truth; if its rewrite is still contradicted, it is deleted.
    """
    pieces = sentences(draft)
    corrections, made = _claims_reply(llm.generate_content(claims_prompt(brief, pieces)).text)
    pieces = _corrected(pieces, corrections)

    false = board_claims.check(board, lines, made).false
    if not false:
        return "".join(pieces)

    flagged = {f.sentence for f in false}
    corrections, made = _claims_reply(llm.generate_content(fix_prompt(brief, pieces, false)).text)
    # Only the flagged sentences may change on the second pass.
    pieces = _corrected(pieces, {k: v for k, v in corrections.items() if str(k).isdigit() and int(k) in flagged})
    still = {f.sentence for f in board_claims.check(board, lines, made).false} & flagged
    return "".join(_corrected(pieces, {str(n): "" for n in still}))
