import { describe, expect, it } from "vitest";
import { grade, isDue } from "./scheduler";

const t0 = new Date("2026-10-24T10:00:00Z");
const minutes = (n: number) => new Date(t0.getTime() + n * 60_000);
const days = (n: number) => new Date(t0.getTime() + n * 86_400_000);

describe("grade", () => {
  it("a missed new card comes back within minutes", () => {
    const s = grade(undefined, false, t0);
    expect(new Date(s.due).getTime()).toBeLessThanOrEqual(minutes(10).getTime());
  });

  it("a new card answered right is not shown again the same day", () => {
    const s = grade(undefined, true, t0);
    expect(new Date(s.due).getTime()).toBeGreaterThan(days(1).getTime() - 1);
  });

  it("a known card drifts further out each time", () => {
    let s = grade(undefined, true, t0);
    s = grade(s, true, new Date(s.due));
    const first = new Date(s.due).getTime() - t0.getTime();
    s = grade(s, true, new Date(s.due));
    const later = new Date(s.due).getTime() - t0.getTime();
    expect(later).toBeGreaterThan(first);
  });

  it("missing a well-known card brings it back soon", () => {
    let s = grade(undefined, true, t0);
    for (let i = 0; i < 4; i++) s = grade(s, true, new Date(s.due));
    const reviewAt = new Date(s.due);
    const lapsed = grade(s, false, reviewAt);
    expect(new Date(lapsed.due).getTime() - reviewAt.getTime()).toBeLessThan(86_400_000);
  });

  it("stores only JSON-safe values", () => {
    const s = grade(undefined, true, t0);
    expect(JSON.parse(JSON.stringify(s))).toEqual(s);
  });
});

describe("isDue", () => {
  it("is due once its time has come", () => {
    const s = grade(undefined, true, t0);
    expect(isDue(s, minutes(1))).toBe(false);
    expect(isDue(s, days(30))).toBe(true);
  });

  it("can look ahead a little", () => {
    const s = grade(undefined, false, t0);
    expect(isDue(s, t0)).toBe(false);
    expect(isDue(s, t0, 20 * 60_000)).toBe(true);
  });
});
