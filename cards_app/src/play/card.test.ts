import { describe, expect, it } from "vitest";
import type { CardDef } from "../deck";
import { attempt, frames, isAnswer, puzzle, splitLesson, targets, task } from "./card";

const base = {
  question: "q",
  answer: ["a"],
  tags: [],
  played_on: "2026-05-01",
  link: "https://lichess.org/g#6",
  commentary: null,
};

// 1.e4 e5 2.Bc4 Nc6 3.Qh5: Black to move, Qxf7# is threatened.
const threat: CardDef = {
  ...base,
  id: "g-5",
  kind: "missed_threat",
  fen: "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3",
  orientation: "black",
  shown_move: null,
  arrows: [{ move: "h5f7", role: "threat" }, { move: "g7g6", role: "best" }],
  line_fen: "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
  line: ["h5f7"],
};

// 1.e4 Nf6 2.d3: Black is about to play 2...Nxe4, which allows 3.dxe4.
const allowed: CardDef = {
  ...base,
  id: "h-3",
  kind: "allowed_tactic",
  fen: "rnbqkb1r/pppppppp/5n2/8/4P3/3P4/PPP2PPP/RNBQKBNR b KQkq - 0 2",
  orientation: "black",
  shown_move: "f6e4",
  arrows: [{ move: "f6e4", role: "played" }, { move: "d3e4", role: "threat" }, { move: "d7d5", role: "best" }],
  line_fen: "rnbqkb1r/pppppppp/8/8/4n3/3P4/PPP2PPP/RNBQKBNR w KQkq - 0 3",
  line: ["d3e4", "d7d5"],
};

// White to move after 2...Nxe4: take the knight.
const tactic: CardDef = {
  ...allowed,
  id: "k-4",
  kind: "missed_tactic",
  fen: allowed.line_fen,
  orientation: "white",
  shown_move: null,
  arrows: [{ move: "d3e4", role: "best" }],
  line_fen: allowed.line_fen,
  line: ["d3e4"],
};

describe("what the player is asked to do", () => {
  it("plays the opponent's threat, from the position with the opponent to move", () => {
    expect(task(threat)).toBe("Play White's threat");
    expect(puzzle(threat)).toEqual({ fen: threat.line_fen, lastMove: null });
  });

  it("plays the reply to the move about to be made, shown as the last move", () => {
    expect(task(allowed)).toBe("Play White's best reply");
    expect(puzzle(allowed)).toEqual({ fen: allowed.line_fen, lastMove: ["f6", "e4"] });
  });

  it("finds their own best move", () => {
    expect(task(tactic)).toBe("Find White's best move");
    expect(puzzle(tactic).fen).toBe(tactic.fen);
  });
});

describe("making a move", () => {
  it("lists where a piece can go", () => {
    expect(targets(tactic.fen, "d3").sort()).toEqual(["d4", "e4"]);
    expect(targets(tactic.fen, "e4")).toEqual([]); // not the side to move
  });

  it("returns the move, or null when it is illegal", () => {
    expect(attempt(tactic.fen, "d3", "e4")).toEqual({ uci: "d3e4", san: "dxe4" });
    expect(attempt(tactic.fen, "d3", "d5")).toBeNull();
  });

  it("promotes to a queen", () => {
    expect(attempt("8/4P3/8/8/8/8/k7/4K3 w - - 0 1", "e7", "e8")?.uci).toBe("e7e8q");
  });

  it("is right only with the line's first move", () => {
    expect(isAnswer(tactic, "d3e4")).toBe(true);
    expect(isAnswer(tactic, "d3d4")).toBe(false);
  });
});

describe("replaying the answer", () => {
  it("starts on the card's position with its arrows, then plays the line", () => {
    const f = frames(threat);
    expect(f.map((x) => x.caption)).toEqual(["Start", "4. Qxf7#"]);
    expect(f[0]).toMatchObject({ fen: threat.fen, arrows: threat.arrows, lastMove: null });
    expect(f[1].lastMove).toEqual(["h5", "f7"]);
  });

  it("plays the move about to be made before the reply", () => {
    expect(frames(allowed).map((x) => x.caption)).toEqual(["Start", "2...Nxe4", "3. dxe4", "3...d5"]);
  });
});

describe("splitLesson", () => {
  it("separates the lesson line", () => {
    expect(splitLesson("Why it works.\n\nLesson: Check every capture.")).toEqual({
      body: "Why it works.",
      lesson: "Check every capture.",
    });
  });

  it("has no lesson when the text has none", () => {
    expect(splitLesson("Why it works.")).toEqual({ body: "Why it works.", lesson: null });
  });
});
