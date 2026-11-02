import { describe, expect, it } from "vitest";
import { message } from "./newGames";

const finished = (state: "done" | "partial" | "failed", cards: number) => ({ state, finished: "2026-10-25T15:30:00", cards });

describe("message", () => {
  it("says it's working while the Mac runs the update", () => {
    expect(message({ state: "running" }, 548)).toMatch(/^Getting your new games/);
  });

  it("counts the new cards", () => {
    expect(message(finished("done", 551), 548)).toBe("3 new cards. Loading them…");
    expect(message(finished("done", 549), 548)).toBe("1 new card. Loading it…");
  });

  it("says when there was nothing new", () => {
    expect(message(finished("done", 548), 548)).toBe("No new cards since last time.");
  });

  it("says when some new cards have no commentary yet", () => {
    expect(message(finished("partial", 550), 548)).toMatch(/^2 new cards\. Some have no commentary yet/);
  });

  it("points to the log when it failed", () => {
    expect(message(finished("failed", 548), 548)).toMatch(/update\.log/);
  });
});
