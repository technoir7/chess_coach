// Playing a card: what to find, whether a move finds it, and the answer
// replayed move by move. Pure; the board component only draws.
import { Chess, type Square } from "chess.js";
import type { Arrow, CardDef } from "../deck";

export type SquarePair = [string, string];

export interface Frame {
  fen: string;
  lastMove: SquarePair | null;
  arrows: Arrow[];
  caption: string;
}

const SIDE = { w: "White", b: "Black" } as const;

// A threat is asked from the card's position with the opponent to move,
// which can be a position no game reaches; chess.js still plays it.
const load = (fen: string) => new Chess(fen, { skipValidation: true });

const squares = (uci: string): SquarePair => [uci.slice(0, 2), uci.slice(2, 4)];

export function task(card: CardDef): string {
  const side = SIDE[load(card.line_fen).turn()];
  if (card.kind === "missed_threat") return `Play ${side}'s threat`;
  if (card.kind === "allowed_tactic") return `Play ${side}'s best reply`;
  return `Find ${side}'s best move`;
}

export function puzzle(card: CardDef): { fen: string; lastMove: SquarePair | null } {
  return { fen: card.line_fen, lastMove: card.shown_move ? squares(card.shown_move) : null };
}

export function targets(fen: string, from: string): string[] {
  return load(fen).moves({ square: from as Square, verbose: true }).map((m) => m.to);
}

/** The move from one square to another, promoting to a queen; null if illegal. */
export function attempt(fen: string, from: string, to: string): { uci: string; san: string } | null {
  const board = load(fen);
  const move = board.moves({ square: from as Square, verbose: true }).find(
    (m) => m.to === to && (!m.promotion || m.promotion === "q"),
  );
  return move ? { uci: move.lan, san: move.san } : null;
}

export function isAnswer(card: CardDef, uci: string): boolean {
  return uci === card.line[0];
}

/** Plays `uci` on `board` and names it with its number: "4. Qxf7#" or "2...Nxe4". */
function play(board: Chess, uci: string): string {
  const number = board.moveNumber();
  const white = board.turn() === "w";
  const { san } = board.move(uci);
  return white ? `${number}. ${san}` : `${number}...${san}`;
}

export function frames(card: CardDef): Frame[] {
  const out: Frame[] = [{ fen: card.fen, lastMove: null, arrows: card.arrows, caption: "Start" }];
  if (card.shown_move) {
    const board = load(card.fen);
    const caption = play(board, card.shown_move);
    out.push({ fen: card.line_fen, lastMove: squares(card.shown_move), arrows: [], caption });
  }
  const board = load(card.line_fen);
  for (const uci of card.line) {
    const caption = play(board, uci);
    out.push({ fen: board.fen(), lastMove: squares(uci), arrows: [], caption });
  }
  return out;
}

export function splitLesson(text: string): { body: string; lesson: string | null } {
  const at = text.search(/\n\s*Lesson:/);
  if (at < 0) return { body: text.trim(), lesson: null };
  return { body: text.slice(0, at).trim(), lesson: text.slice(at).replace(/^\s*Lesson:\s*/, "").trim() };
}
