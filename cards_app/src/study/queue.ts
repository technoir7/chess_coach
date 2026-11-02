// Chooses the next card. Pure: same input, same answer.
import { gameOf, type CardDef } from "../deck";
import type { CardOrder, Progress } from "./progress";
import { isDue } from "./scheduler";

// After this many reviews in a row, slip in a new card so learning keeps moving.
const NEW_EVERY = 3;
// When nothing is due, cards coming up within this window may be shown early.
const LEARN_AHEAD_MS = 20 * 60_000;

export interface QueueInput {
  /** Cards to choose from, already filtered, newest game first. */
  cards: CardDef[];
  progress: Progress;
  now: Date;
  /** How many more new cards may be introduced today. */
  newLimit: number;
  /** Card ids shown this session, most recent last. */
  recent: string[];
  /** Reviews shown since the last new card this session. */
  sinceNew: number;
  order: CardOrder;
  /** Which shuffle to use when order is "random". */
  seed: number;
}

export interface Pick {
  card: CardDef;
  kind: "due" | "new" | "ahead";
}

export function pickNext({ cards, progress, now, newLimit, recent, sinceNew, order, seed }: QueueInput): Pick | null {
  const saved = progress.cards;
  const byDue = (a: CardDef, b: CardDef) => Date.parse(saved[a.id].due) - Date.parse(saved[b.id].due);

  const due = cards.filter((c) => saved[c.id] && isDue(saved[c.id], now)).sort(byDue);
  const fresh = newLimit > 0 ? cards.filter((c) => !saved[c.id]) : [];

  if (fresh.length && (!due.length || sinceNew >= NEW_EVERY)) {
    const ranked = order === "random" ? [...fresh].sort((a, b) => shuffleKey(a.id, seed) - shuffleKey(b.id, seed)) : fresh;
    return { card: varied(ranked, cards, recent), kind: "new" };
  }
  if (due.length) return { card: varied(due, cards, recent), kind: "due" };

  const ahead = cards.filter((c) => saved[c.id] && isDue(saved[c.id], now, LEARN_AHEAD_MS)).sort(byDue);
  return ahead.length ? { card: varied(ahead, cards, recent), kind: "ahead" } : null;
}

/** FNV-1a hash of seed + id: a cheap, stable stand-in for a random rank. */
function shuffleKey(id: string, seed: number): number {
  let h = 0x811c9dc5;
  for (const ch of `${seed}:${id}`) h = Math.imul(h ^ ch.charCodeAt(0), 0x01000193);
  return h >>> 0;
}

/** First candidate not from the same game as the last card, if any: two cards from one game give each other away. */
function varied(candidates: CardDef[], all: CardDef[], recent: string[]): CardDef {
  const last = all.find((c) => c.id === recent[recent.length - 1]);
  const notLast = candidates.filter((c) => c.id !== last?.id);
  if (!notLast.length) return candidates[0];
  return notLast.find((c) => !last || gameOf(c) !== gameOf(last)) ?? notLast[0];
}
