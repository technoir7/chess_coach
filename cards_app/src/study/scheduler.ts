// Spaced repetition via ts-fsrs. The app grades with two buttons only, so
// "missed" maps to Again and "got it" to Good; Hard and Easy are never used.
import { createEmptyCard, fsrs, Rating, type Card } from "ts-fsrs";

/** A card's schedule as stored on the device: ts-fsrs's Card with dates as ISO strings. */
export interface SavedCard {
  due: string;
  stability: number;
  difficulty: number;
  elapsed_days: number;
  scheduled_days: number;
  learning_steps: number;
  reps: number;
  lapses: number;
  state: number;
  last_review?: string;
}

// One short learning step: a missed new card returns in a minute, but a new
// card answered right goes straight out for days. The default second step
// (10 min) made every new card repeat within the same short session.
const scheduler = fsrs({ enable_fuzz: true, learning_steps: ["1m"] });

function toSaved(card: Card): SavedCard {
  const { due, last_review, ...rest } = card;
  return { ...rest, due: due.toISOString(), ...(last_review ? { last_review: last_review.toISOString() } : {}) };
}

export function grade(saved: SavedCard | undefined, gotIt: boolean, now: Date): SavedCard {
  const card = saved ?? toSaved(createEmptyCard(now));
  const { card: next } = scheduler.next(card, now, gotIt ? Rating.Good : Rating.Again);
  return toSaved(next);
}

export function isDue(saved: SavedCard, now: Date, aheadMs = 0): boolean {
  return new Date(saved.due).getTime() <= now.getTime() + aheadMs;
}
