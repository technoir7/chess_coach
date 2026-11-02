// Everything the app remembers, as one JSON-safe value. All updates are
// pure; saving to the device happens in storage.ts.
import type { Kind } from "../deck";
import { studyDay } from "./day";
import { grade, type SavedCard } from "./scheduler";

export interface DayCount {
  reviews: number;
  new: number;
  extraNew: number;
}

/** How new cards are chosen: newest game first, or shuffled. */
export type CardOrder = "newest" | "random";
export const CARD_ORDERS: CardOrder[] = ["newest", "random"];

export interface Settings {
  newPerDay: number;
  kind: Kind | "all";
  order: CardOrder;
  /** Picks which shuffle "random" uses; a new seed reshuffles. */
  seed: number;
}

export interface Progress {
  version: 1;
  cards: Record<string, SavedCard>;
  days: Record<string, DayCount>;
  flags: Record<string, string>;
  settings: Settings;
}

const DEFAULT_SETTINGS: Settings = { newPerDay: 10, kind: "all", order: "newest", seed: 1 };
const KINDS = ["all", "missed_threat", "allowed_tactic", "missed_tactic"];

export function emptyProgress(): Progress {
  return { version: 1, cards: {}, days: {}, flags: {}, settings: { ...DEFAULT_SETTINGS } };
}

function today(p: Progress, now: Date): DayCount {
  return p.days[studyDay(now)] ?? { reviews: 0, new: 0, extraNew: 0 };
}

function withToday(p: Progress, now: Date, day: DayCount): Progress {
  return { ...p, days: { ...p.days, [studyDay(now)]: day } };
}

export function recordAnswer(p: Progress, cardId: string, gotIt: boolean, now: Date): Progress {
  const isNew = !(cardId in p.cards);
  const day = today(p, now);
  return withToday(
    { ...p, cards: { ...p.cards, [cardId]: grade(p.cards[cardId], gotIt, now) } },
    now,
    { ...day, reviews: day.reviews + 1, new: day.new + (isNew ? 1 : 0) },
  );
}

export function newAllowance(p: Progress, now: Date): number {
  const day = today(p, now);
  return Math.max(0, p.settings.newPerDay + day.extraNew - day.new);
}

export function reviewsToday(p: Progress, now: Date): number {
  return today(p, now).reviews;
}

export function addExtraNew(p: Progress, n: number, now: Date): Progress {
  const day = today(p, now);
  // Extra cards top up from where today stands, so "5 more" always means 5 more.
  const shortfall = Math.max(0, day.new - p.settings.newPerDay - day.extraNew);
  return withToday(p, now, { ...day, extraNew: day.extraNew + shortfall + n });
}

export function toggleFlag(p: Progress, cardId: string, now: Date): Progress {
  const flags = { ...p.flags };
  if (cardId in flags) delete flags[cardId];
  else flags[cardId] = now.toISOString();
  return { ...p, flags };
}

export function updateSettings(p: Progress, settings: Partial<Settings>): Progress {
  return { ...p, settings: { ...p.settings, ...settings } };
}

/** Validate a stored or imported value. Throws with a reason rather than guessing. */
export function parseProgress(value: unknown): Progress {
  const fail = (why: string): never => {
    throw new Error(`Not a valid backup: ${why}`);
  };
  if (typeof value !== "object" || value === null) fail("not an object");
  const v = value as Record<string, unknown>;
  if (v.version !== 1) fail(`unknown version ${String(v.version)}`);
  for (const key of ["cards", "days", "flags"] as const) {
    if (typeof v[key] !== "object" || v[key] === null) fail(`missing ${key}`);
  }
  for (const [id, c] of Object.entries(v.cards as Record<string, Partial<SavedCard>>)) {
    if (typeof c?.due !== "string" || Number.isNaN(Date.parse(c.due)) || typeof c.stability !== "number") {
      fail(`card ${id} has a broken schedule`);
    }
  }
  const settings = { ...DEFAULT_SETTINGS, ...(typeof v.settings === "object" && v.settings !== null ? v.settings : {}) };
  if (!CARD_ORDERS.includes(settings.order)) fail(`unknown card order ${JSON.stringify(settings.order)}`);
  if (!KINDS.includes(settings.kind)) fail(`unknown card kind ${JSON.stringify(settings.kind)}`);
  return {
    version: 1,
    cards: v.cards as Progress["cards"],
    days: v.days as Progress["days"],
    flags: v.flags as Progress["flags"],
    settings: settings as Settings,
  };
}
