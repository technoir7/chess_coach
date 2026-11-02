// One card: find the move on the board, then step through the answer.
import { useMemo, useState } from "react";
import { KINDS, type CardDef } from "../deck";
import { attempt, frames, isAnswer, puzzle, splitLesson, targets, task } from "../play/card";
import type { Pick } from "../study/queue";
import { Board } from "./Board";

export interface Outcome {
  /** The move tried, or null when the answer was shown without one. */
  san: string | null;
  right: boolean;
}

interface Props {
  pick: Pick;
  outcome: Outcome | null;
  flagged: boolean;
  onOutcome: (o: Outcome) => void;
  onFlag: () => void;
}

export function CardView({ pick, outcome, flagged, onOutcome, onFlag }: Props) {
  const { card, kind } = pick;
  return (
    <article className="card">
      <header className="card-meta">
        <span className="card-type">{KINDS.find((k) => k.id === card.kind)?.label}</span>
        {kind === "new" && <span className="badge">new</span>}
        <span className="when">{tagLine(card)}</span>
      </header>
      {outcome ? (
        <Answer card={card} outcome={outcome} flagged={flagged} onFlag={onFlag} />
      ) : (
        <Question card={card} onOutcome={onOutcome} />
      )}
    </article>
  );
}

function Question({ card, onOutcome }: { card: CardDef; onOutcome: (o: Outcome) => void }) {
  const { fen, lastMove } = puzzle(card);
  const [selected, setSelected] = useState<string | null>(null);
  const reachable = selected ? targets(fen, selected) : [];

  const tap = (square: string) => {
    if (selected && reachable.includes(square)) {
      const move = attempt(fen, selected, square)!;
      onOutcome({ san: move.san, right: isAnswer(card, move.uci) });
      return;
    }
    setSelected(square !== selected && targets(fen, square).length ? square : null);
  };

  return (
    <>
      <Board fen={fen} orientation={card.orientation} lastMove={lastMove} selected={selected} targets={reachable} onSquare={tap} />
      <p className="card-front">{card.question}</p>
      <p className="task">{task(card)} on the board.</p>
      <button className="link-button" onClick={() => onOutcome({ san: null, right: false })}>
        I don't know: show me
      </button>
    </>
  );
}

function Answer({ card, outcome, flagged, onFlag }: { card: CardDef; outcome: Outcome; flagged: boolean; onFlag: () => void }) {
  const steps = useMemo(() => frames(card), [card]);
  // Open on the answer's first move: it's what was being asked for.
  const [index, setIndex] = useState(card.shown_move ? 2 : 1);
  const frame = steps[index];
  const note = card.commentary ? splitLesson(card.commentary) : null;
  const answerMove = steps[card.shown_move ? 2 : 1].caption;

  return (
    <>
      <Board fen={frame.fen} orientation={card.orientation} lastMove={frame.lastMove} arrows={frame.arrows} />
      <div className="stepper-row">
        <button onClick={() => setIndex(Math.max(0, index - 1))} disabled={index === 0} aria-label="Back">◀</button>
        <span className="frame-caption">{frame.caption}</span>
        <button onClick={() => setIndex(Math.min(steps.length - 1, index + 1))} disabled={index === steps.length - 1} aria-label="Forward">▶</button>
      </div>

      <p className={`verdict ${outcome.right ? "is-right" : "is-wrong"}`}>
        {outcome.right
          ? `✓ ${answerMove} is right.`
          : outcome.san
            ? `✗ You played ${outcome.san}. The answer is ${answerMove}.`
            : `The answer is ${answerMove}.`}
      </p>

      <div className="card-back">
        {card.answer.map((line) => <p key={line} className="answer-line">{line}</p>)}
        {note && (
          <div className="coach">
            <p>{note.body}</p>
            {note.lesson && <p className="lesson"><strong>Lesson:</strong> {note.lesson}</p>}
          </div>
        )}
        <footer className="card-foot">
          <a href={card.link} target="_blank" rel="noreferrer">Open the game</a>
          <button className={`flag ${flagged ? "is-on" : ""}`} onClick={onFlag} aria-pressed={flagged}>
            {flagged ? "⚑ Flagged" : "⚐ Flag"}
          </button>
        </footer>
      </div>
    </>
  );
}

function tagLine(card: CardDef): string {
  const speed = card.tags.find((t) => ["bullet", "blitz", "rapid", "classical", "correspondence"].includes(t));
  const month = new Date(card.played_on).toLocaleDateString(undefined, { month: "short", year: "numeric" });
  return [speed, month].filter(Boolean).join(" · ");
}
