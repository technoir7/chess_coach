// Draws a position. Tapping a square reports it; what a tap means is up to the caller.
import { Chess } from "chess.js";
import type { Arrow, Role } from "../deck";
import type { SquarePair } from "../play/card";

const FILES = "abcdefgh";
const ARROW_COLOR: Record<Role, string> = { threat: "#cc0000", best: "#15781b", played: "#1f5fbf" };

interface Props {
  fen: string;
  orientation: "white" | "black";
  lastMove?: SquarePair | null;
  arrows?: Arrow[];
  selected?: string | null;
  targets?: string[];
  onSquare?: (square: string) => void;
}

export function Board({ fen, orientation, lastMove, arrows = [], selected, targets = [], onSquare }: Props) {
  const flip = orientation === "black";
  // Square name to its top-left corner on an 8x8 grid, as seen from the player's side.
  const at = (square: string) => {
    const file = FILES.indexOf(square[0]);
    const rank = Number(square[1]) - 1;
    return { x: flip ? 7 - file : file, y: flip ? rank : 7 - rank };
  };
  const rows = new Chess(fen, { skipValidation: true }).board();
  const squares = [];
  for (let rank = 0; rank < 8; rank++) {
    for (let file = 0; file < 8; file++) squares.push(`${FILES[file]}${rank + 1}`);
  }

  return (
    <svg className="board" viewBox="0 0 8 8" role="img" aria-label={`Board: ${fen}`}>
      <defs>
        {(Object.keys(ARROW_COLOR) as Role[]).map((role) => (
          <marker key={role} id={`head-${role}`} viewBox="0 0 4 4" refX="2" refY="2" markerWidth="2.2" markerHeight="2.2" orient="auto">
            <path d="M0,0 L4,2 L0,4 z" fill={ARROW_COLOR[role]} />
          </marker>
        ))}
      </defs>
      {squares.map((sq) => {
        const { x, y } = at(sq);
        const dark = (FILES.indexOf(sq[0]) + Number(sq[1])) % 2 === 1;
        const marked = lastMove?.includes(sq);
        return (
          <g key={sq} onClick={onSquare ? () => onSquare(sq) : undefined}>
            <rect x={x} y={y} width="1" height="1" className={dark ? "sq-dark" : "sq-light"} />
            {marked && <rect x={x} y={y} width="1" height="1" className="sq-last" />}
            {sq === selected && <rect x={x} y={y} width="1" height="1" className="sq-selected" />}
            {y === 7 && <text x={x + 0.94} y={y + 0.95} className={`coord ${dark ? "on-dark" : "on-light"}`} textAnchor="end">{sq[0]}</text>}
            {x === 0 && <text x={x + 0.05} y={y + 0.22} className={`coord ${dark ? "on-dark" : "on-light"}`}>{sq[1]}</text>}
          </g>
        );
      })}
      {rows.flat().map((piece) => {
        if (!piece) return null;
        const { x, y } = at(piece.square);
        const name = `${piece.color}${piece.type.toUpperCase()}`;
        return <image key={piece.square} href={`/pieces/${name}.svg`} x={x} y={y} width="1" height="1" pointerEvents="none" />;
      })}
      {targets.map((sq) => {
        const { x, y } = at(sq);
        return <circle key={sq} cx={x + 0.5} cy={y + 0.5} r="0.16" className="target" pointerEvents="none" />;
      })}
      {arrows.map(({ move, role }) => {
        const from = at(move.slice(0, 2));
        const to = at(move.slice(2, 4));
        // Stop short of the centre so the head doesn't hide the piece.
        const dx = to.x - from.x;
        const dy = to.y - from.y;
        const len = Math.hypot(dx, dy);
        const end = (len - 0.35) / len;
        return (
          <line
            key={move + role}
            x1={from.x + 0.5}
            y1={from.y + 0.5}
            x2={from.x + 0.5 + dx * end}
            y2={from.y + 0.5 + dy * end}
            stroke={ARROW_COLOR[role]}
            strokeWidth="0.16"
            strokeOpacity="0.8"
            strokeLinecap="round"
            markerEnd={`url(#head-${role})`}
            pointerEvents="none"
          />
        );
      })}
    </svg>
  );
}
