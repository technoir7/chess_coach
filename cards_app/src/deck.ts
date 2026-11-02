// The cards, as make_cards.py writes them (src/games/app_deck.py), newest game first.
import raw from "./generated/deck.json";

export type Kind = "missed_threat" | "allowed_tactic" | "missed_tactic";
export type Role = "threat" | "best" | "played";

export interface Arrow {
  move: string;
  role: Role;
}

export interface CardDef {
  id: string;
  kind: Kind;
  /** The position on the card, the player to move. */
  fen: string;
  orientation: "white" | "black";
  question: string;
  /** The move about to be played, for "what does it allow?" cards. */
  shown_move: string | null;
  answer: string[];
  arrows: Arrow[];
  /** Where the answer's line starts; its first move is the one to find. */
  line_fen: string;
  line: string[];
  tags: string[];
  played_on: string;
  link: string;
  commentary: string | null;
}

export const KINDS: { id: Kind; label: string }[] = [
  { id: "missed_threat", label: "Their threats" },
  { id: "allowed_tactic", label: "What my move allows" },
  { id: "missed_tactic", label: "My tactics" },
];

const KIND_IDS = new Set<string>(KINDS.map((k) => k.id));

/** Checks the generated deck at the boundary, so a bad export fails loudly at startup. */
export function parseDeck(value: unknown): CardDef[] {
  const cards = (value as { cards?: unknown })?.cards;
  if (!Array.isArray(cards)) throw new Error("deck.json has no cards list");
  for (const c of cards as Partial<CardDef>[]) {
    const where = `deck.json card ${String(c?.id)}`;
    if (typeof c?.id !== "string" || typeof c.fen !== "string" || typeof c.line_fen !== "string") {
      throw new Error(`${where}: missing id or position`);
    }
    if (!KIND_IDS.has(c.kind as string)) throw new Error(`${where}: unknown kind ${String(c.kind)}`);
    if (!Array.isArray(c.line) || c.line.length === 0) throw new Error(`${where}: no line to play`);
  }
  return cards as CardDef[];
}

export const deck: CardDef[] = parseDeck(raw);

/** The game a card comes from: its id is "<game id>-<ply>". */
export function gameOf(card: CardDef): string {
  return card.id.slice(0, card.id.lastIndexOf("-"));
}
