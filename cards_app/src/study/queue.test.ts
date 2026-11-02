import { describe, expect, it } from "vitest";
import type { CardDef } from "../deck";
import { emptyProgress, recordAnswer, type Progress } from "./progress";
import { pickNext } from "./queue";

const t0 = new Date(2026, 9, 24, 12, 0);
const later = (days: number) => new Date(t0.getTime() + days * 86_400_000);

/** ids are "<game>-<ply>", as in the deck. */
const card = (id: string): CardDef => ({
  id,
  kind: "missed_tactic",
  fen: "",
  orientation: "white",
  question: "q",
  shown_move: null,
  answer: [],
  arrows: [],
  line_fen: "",
  line: ["e2e4"],
  tags: [],
  played_on: "2026-01-01",
  link: "",
  commentary: null,
});

function seen(p: Progress, ids: string[], at = t0): Progress {
  return ids.reduce((acc, id) => recordAnswer(acc, id, true, at), p);
}

/** Seen, and not coming back for a while. */
function learned(p: Progress, ids: string[]): Progress {
  const q = seen(p, ids);
  const cards = { ...q.cards };
  for (const id of ids) cards[id] = { ...cards[id], due: later(10).toISOString() };
  return { ...q, cards };
}

const base = { recent: [] as string[], sinceNew: 0, newLimit: 10, order: "newest" as const, seed: 1 };

describe("pickNext", () => {
  it("starts with the newest game's card", () => {
    const cards = [card("new-10"), card("old-4")];
    expect(pickNext({ ...base, cards, progress: emptyProgress(), now: t0 })?.card.id).toBe("new-10");
  });

  it("doesn't follow a card with another from the same game when it can avoid it", () => {
    const cards = [card("a-10"), card("a-20"), card("b-5")];
    const progress = learned(emptyProgress(), ["a-10"]);
    expect(pickNext({ ...base, cards, progress, now: t0, recent: ["a-10"] })?.card.id).toBe("b-5");
  });

  it("random: picks new cards from anywhere, the same way for the same shuffle", () => {
    const cards = Array.from({ length: 40 }, (_, i) => card(`g${i}-1`));
    const run = (seed: number) => {
      const order: string[] = [];
      let progress = emptyProgress();
      for (let i = 0; i < 8; i++) {
        const next = pickNext({ ...base, order: "random", seed, cards, progress, now: t0, recent: order })!;
        order.push(next.card.id);
        progress = learned(progress, [next.card.id]);
      }
      return order;
    };
    expect(run(1)).toEqual(run(1));
    expect(run(1)).not.toEqual(run(2));
    expect(run(1)).not.toEqual(cards.slice(0, 8).map((c) => c.id));
  });

  it("offers nothing new once today's allowance is used", () => {
    const cards = [card("a-1"), card("b-1")];
    const progress = learned(emptyProgress(), ["a-1"]);
    expect(pickNext({ ...base, cards, progress, now: t0, newLimit: 0 })).toBeNull();
  });

  it("shows the most overdue card first", () => {
    const cards = [card("a-1"), card("b-1"), card("c-1")];
    let progress = seen(emptyProgress(), ["a-1"], t0);
    progress = seen(progress, ["b-1"], later(-5));
    const next = pickNext({ ...base, cards, progress, now: later(30), newLimit: 0 });
    expect(next).toMatchObject({ card: { id: "b-1" }, kind: "due" });
  });

  it("mixes in a new card after a few reviews", () => {
    const cards = [card("a-1"), card("b-1"), card("c-1"), card("n-1")];
    const progress = seen(emptyProgress(), ["a-1", "b-1", "c-1"], later(-30));
    expect(pickNext({ ...base, cards, progress, now: t0, sinceNew: 0 })?.kind).toBe("due");
    expect(pickNext({ ...base, cards, progress, now: t0, sinceNew: 3 })?.card.id).toBe("n-1");
  });

  it("never repeats the card just shown if anything else is available", () => {
    const cards = [card("a-1"), card("b-1")];
    const progress = seen(emptyProgress(), ["a-1", "b-1"], later(-30));
    const next = pickNext({ ...base, cards, progress, now: t0, newLimit: 0, recent: ["b-1"] });
    expect(next?.card.id).toBe("a-1");
  });

  it("when nothing is due, brings forward cards due in the next few minutes", () => {
    const cards = [card("a-1")];
    const progress = recordAnswer(emptyProgress(), "a-1", false, t0);
    const next = pickNext({ ...base, cards, progress, now: new Date(t0.getTime() + 1000), newLimit: 0 });
    expect(next?.card.id).toBe("a-1");
  });

  it("is done when nothing is due soon and nothing new is allowed", () => {
    const cards = [card("a-1")];
    const progress = learned(emptyProgress(), ["a-1"]);
    expect(pickNext({ ...base, cards, progress, now: t0, newLimit: 0 })).toBeNull();
  });
});
