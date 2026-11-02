import { describe, expect, it } from "vitest";
import { deck, gameOf, parseDeck } from "./deck";
import { attempt, frames } from "./play/card";

describe("parseDeck", () => {
  it("rejects a deck that isn't one, loudly", () => {
    expect(() => parseDeck({})).toThrow(/cards/);
    expect(() => parseDeck({ cards: [{ id: "a-1", fen: "x", line_fen: "x", kind: "quiet", line: ["e2e4"] }] })).toThrow(/kind/);
    expect(() => parseDeck({ cards: [{ id: "a-1", fen: "x", line_fen: "x", kind: "missed_tactic", line: [] }] })).toThrow(/line/);
  });
});

describe("the generated deck", () => {
  it("replays every card, and each answer can be played on the board by tapping", () => {
    for (const card of deck) {
      expect(() => frames(card), card.id).not.toThrow();
      const first = card.line[0];
      expect(attempt(card.line_fen, first.slice(0, 2), first.slice(2, 4))?.uci.slice(0, 4), card.id).toBe(first.slice(0, 4));
    }
  });

  it("names each card's game", () => {
    expect(gameOf({ ...deck[0], id: "GQHt6n9x-40" })).toBe("GQHt6n9x");
  });
});
