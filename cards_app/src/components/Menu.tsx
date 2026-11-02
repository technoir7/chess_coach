import { useRef, useState } from "react";
import { deck, KINDS } from "../deck";
import type { CardOrder, Progress } from "../study/progress";
import { NewGames } from "./NewGames";

const ORDER_LABEL: Record<CardOrder, string> = { newest: "Newest first", random: "Random" };
const ORDER_HINT: Record<CardOrder, string> = {
  newest: "Your most recent games first: those habits are the ones to fix.",
  random: "From any game. Tap Random again to reshuffle.",
};

interface Props {
  progress: Progress;
  onClose: () => void;
  onNewPerDay: (n: number) => void;
  onOrder: (order: CardOrder) => void;
  onExport: () => Promise<void>;
  onImport: (file: File) => Promise<void>;
}

export function Menu({ progress, onClose, onNewPerDay, onOrder, onExport, onImport }: Props) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const byKind = KINDS.map((k) => {
    const ids = deck.filter((c) => c.kind === k.id).map((c) => c.id);
    return { ...k, total: ids.length, seen: ids.filter((id) => id in progress.cards).length };
  });
  const totalSeen = deck.filter((c) => c.id in progress.cards).length;

  const flagged = deck.filter((c) => c.id in progress.flags);
  const copyFlags = async () => {
    await navigator.clipboard.writeText(flagged.map((c) => `${c.id}: ${c.question}`).join("\n"));
    setCopied(true);
  };

  const run = async (label: string, action: () => Promise<void>) => {
    setStatus(null);
    try {
      await action();
      setStatus(`${label}: done`);
    } catch (e) {
      setStatus(`${label} failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  return (
    <div className="menu">
      <header className="topbar">
        <h1>Chess cards</h1>
        <button className="ghost" onClick={onClose}>Done</button>
      </header>

      <section>
        <h2>New games</h2>
        <NewGames />
      </section>

      <section>
        <h2>New cards per day</h2>
        <div className="stepper">
          <button onClick={() => onNewPerDay(Math.max(0, progress.settings.newPerDay - 5))}>−</button>
          <span>{progress.settings.newPerDay}</span>
          <button onClick={() => onNewPerDay(progress.settings.newPerDay + 5)}>+</button>
        </div>
      </section>

      <section>
        <h2>Order of new cards</h2>
        <div className="segmented" role="group" aria-label="Order of new cards">
          {(Object.keys(ORDER_LABEL) as CardOrder[]).map((o) => (
            <button key={o} aria-pressed={progress.settings.order === o} onClick={() => onOrder(o)}>
              {ORDER_LABEL[o]}
            </button>
          ))}
        </div>
        <p className="muted small">{ORDER_HINT[progress.settings.order]} Cards you've seen still come back when due.</p>
      </section>

      <section>
        <h2>Seen so far</h2>
        <p className="muted">{totalSeen} of {deck.length} cards</p>
        <ul className="bars">
          {byKind.map((k) => (
            <li key={k.id}>
              <span>{k.label}</span>
              <span className="bar"><span style={{ width: `${(100 * k.seen) / k.total}%` }} /></span>
              <span className="muted">{k.seen}/{k.total}</span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Flagged cards ({flagged.length})</h2>
        {flagged.length === 0 ? (
          <p className="muted">Flag a card from its answer side if something on it is wrong.</p>
        ) : (
          <>
            <ul className="flag-list">
              {flagged.map((c) => <li key={c.id}>{c.question}</li>)}
            </ul>
            <button onClick={copyFlags}>{copied ? "Copied" : "Copy list"}</button>
          </>
        )}
      </section>

      <section>
        <h2>Backup</h2>
        <p className="muted">Progress lives on this phone only. Save a backup now and then.</p>
        <div className="row">
          <button onClick={() => run("Backup", onExport)}>Save backup</button>
          <button onClick={() => fileInput.current?.click()}>Restore…</button>
        </div>
        <input
          ref={fileInput}
          type="file"
          accept="application/json,.json"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) void run("Restore", () => onImport(file));
          }}
        />
        {status && <p className="status">{status}</p>}
      </section>
    </div>
  );
}
