import { describe, expect, it } from "vitest";
import { addExtraNew, emptyProgress, newAllowance, parseProgress, recordAnswer, toggleFlag } from "./progress";

const t0 = new Date(2026, 9, 24, 12, 0);

describe("recordAnswer", () => {
  it("schedules the card and counts the review for today", () => {
    const p = recordAnswer(emptyProgress(), "a/1", true, t0);
    expect(p.cards["a/1"]).toBeDefined();
    expect(p.days["2026-10-24"]).toMatchObject({ reviews: 1, new: 1 });
  });

  it("counts a card as new only the first time", () => {
    let p = recordAnswer(emptyProgress(), "a/1", false, t0);
    p = recordAnswer(p, "a/1", true, new Date(t0.getTime() + 60_000));
    expect(p.days["2026-10-24"]).toMatchObject({ reviews: 2, new: 1 });
  });

  it("does not mutate its input", () => {
    const before = emptyProgress();
    recordAnswer(before, "a/1", true, t0);
    expect(before).toEqual(emptyProgress());
  });
});

describe("new card allowance", () => {
  it("is the daily setting minus today's new cards, plus any extra asked for", () => {
    let p = emptyProgress();
    p = { ...p, settings: { ...p.settings, newPerDay: 2 } };
    p = recordAnswer(p, "a/1", true, t0);
    expect(newAllowance(p, t0)).toBe(1);
    p = recordAnswer(p, "a/2", true, t0);
    expect(newAllowance(p, t0)).toBe(0);
    p = addExtraNew(p, 5, t0);
    expect(newAllowance(p, t0)).toBe(5);
  });

  it("resets the next day", () => {
    let p = emptyProgress();
    p = { ...p, settings: { ...p.settings, newPerDay: 1 } };
    p = recordAnswer(p, "a/1", true, t0);
    expect(newAllowance(p, new Date(2026, 9, 25, 12, 0))).toBe(1);
  });
});

describe("toggleFlag", () => {
  it("flags and unflags", () => {
    const p = toggleFlag(emptyProgress(), "a/1", t0);
    expect(p.flags["a/1"]).toBeDefined();
    expect(toggleFlag(p, "a/1", t0).flags["a/1"]).toBeUndefined();
  });
});

describe("parseProgress", () => {
  it("round-trips through JSON", () => {
    let p = recordAnswer(emptyProgress(), "a/1", true, t0);
    p = toggleFlag(p, "a/1", t0);
    expect(parseProgress(JSON.parse(JSON.stringify(p)))).toEqual(p);
  });

  it("rejects something that isn't a backup, loudly", () => {
    expect(() => parseProgress({ hello: 1 })).toThrow();
    expect(() => parseProgress({ ...emptyProgress(), version: 99 })).toThrow(/version/);
    expect(() => parseProgress({ ...emptyProgress(), cards: { "a/1": { due: "soon" } } })).toThrow(/a\/1/);
  });

  it("fills in settings added after the backup was made", () => {
    const old = { ...emptyProgress(), settings: {} };
    expect(parseProgress(old).settings).toEqual(emptyProgress().settings);
  });

  it("rejects an unknown card order", () => {
    const bad = { ...emptyProgress(), settings: { ...emptyProgress().settings, order: "sideways" } };
    expect(() => parseProgress(bad)).toThrow(/order/);
  });

  it("rejects an unknown card kind", () => {
    const bad = { ...emptyProgress(), settings: { ...emptyProgress().settings, kind: "quiet" } };
    expect(() => parseProgress(bad)).toThrow(/kind/);
  });
});
