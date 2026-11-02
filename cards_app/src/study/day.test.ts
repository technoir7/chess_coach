import { describe, expect, it } from "vitest";
import { studyDay } from "./day";

describe("studyDay", () => {
  it("uses the local calendar date", () => {
    expect(studyDay(new Date(2026, 9, 24, 15, 0))).toBe("2026-10-24");
  });

  it("is right on the night the clocks go back (Europe, 25 Oct 2026)", () => {
    expect(studyDay(new Date(2026, 9, 25, 3, 30))).toBe("2026-10-24");
    expect(studyDay(new Date(2026, 9, 25, 9, 0))).toBe("2026-10-25");
  });

  it("counts the small hours as the day before, so a late session isn't split", () => {
    expect(studyDay(new Date(2026, 9, 25, 3, 59))).toBe("2026-10-24");
    expect(studyDay(new Date(2026, 9, 25, 4, 0))).toBe("2026-10-25");
  });
});
