import { useEffect, useMemo, useState } from "react";
import { CardView, type Outcome } from "./components/CardView";
import { Menu } from "./components/Menu";
import { NewGames } from "./components/NewGames";
import { deck, KINDS, type Kind } from "./deck";
import {
  addExtraNew,
  newAllowance,
  recordAnswer,
  reviewsToday,
  toggleFlag,
  updateSettings,
  type Progress,
} from "./study/progress";
import { pickNext, type Pick } from "./study/queue";
import {
  clearStoredProgress,
  exportBackup,
  loadProgress,
  rawStoredProgress,
  readBackupFile,
  requestPersistence,
  saveProgress,
} from "./storage";

const EXTRA_NEW = 5;
// Grades that can be taken back, most recent last.
const UNDO_DEPTH = 10;

interface Session {
  recent: string[];
  sinceNew: number;
}

/** Everything as it was just before a grade, so Undo can put it back. */
interface Before {
  progress: Progress;
  session: Session;
  pick: Pick;
  outcome: Outcome;
}

export function App() {
  const [loaded] = useState((): { ok: true; progress: Progress } | { ok: false; error: string } => {
    try {
      return { ok: true, progress: loadProgress() };
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : String(e) };
    }
  });
  if (!loaded.ok) return <BrokenStorage message={loaded.error} />;
  return <Study initial={loaded.progress} />;
}

const cardsOf = (kind: Kind | "all") => (kind === "all" ? deck : deck.filter((c) => c.kind === kind));

function Study({ initial }: { initial: Progress }) {
  const [progress, setProgress] = useState(initial);
  const [session, setSession] = useState<Session>({ recent: [], sinceNew: 0 });
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [view, setView] = useState<"study" | "menu">("study");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [undoable, setUndoable] = useState<Before[]>([]);

  useEffect(() => void requestPersistence(), []);

  const update = (next: Progress) => {
    setProgress(next);
    try {
      saveProgress(next);
      setSaveError(null);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e));
    }
  };

  const kind = progress.settings.kind;
  const cards = useMemo(() => cardsOf(kind), [kind]);

  // Picked once per card shown, not on every render, so the card can't change under the thumb.
  const choose = (p: Progress, s: Session, pool: typeof cards) => {
    const now = new Date();
    const { order, seed } = p.settings;
    return pickNext({ cards: pool, progress: p, now, newLimit: newAllowance(p, now), order, seed, ...s });
  };
  const [pick, setPick] = useState(() => choose(progress, session, cards));
  const repick = (p: Progress, s: Session, pool = cards) => {
    setPick(choose(p, s, pool));
    setOutcome(null);
  };

  const answer = (gotIt: boolean) => {
    if (!pick || !outcome) return;
    setUndoable([...undoable, { progress, session, pick, outcome }].slice(-UNDO_DEPTH));
    const next = recordAnswer(progress, pick.card.id, gotIt, new Date());
    const s = {
      recent: [...session.recent, pick.card.id].slice(-10),
      sinceNew: pick.kind === "new" ? 0 : session.sinceNew + 1,
    };
    update(next);
    setSession(s);
    repick(next, s);
  };

  // Back to the last graded card, answer side up, with the grade taken back.
  const undo = () => {
    const before = undoable[undoable.length - 1];
    if (!before) return;
    update(before.progress);
    setSession(before.session);
    setPick(before.pick);
    setOutcome(before.outcome);
    setUndoable(undoable.slice(0, -1));
  };

  const changeKind = (k: Kind | "all") => {
    const next = updateSettings(progress, { kind: k });
    update(next);
    repick(next, session, cardsOf(k));
  };

  if (view === "menu") {
    return (
      <Menu
        progress={progress}
        onClose={() => {
          setView("study");
          if (!pick) repick(progress, session);
        }}
        onNewPerDay={(n) => update(updateSettings(progress, { newPerDay: n }))}
        onOrder={(order) => {
          // Picking Random again reshuffles.
          const next = updateSettings(progress, order === "random" ? { order, seed: Date.now() } : { order });
          update(next);
          repick(next, session);
        }}
        onExport={() => exportBackup(JSON.stringify(progress), new Date())}
        onImport={async (file) => {
          const restored = await readBackupFile(file);
          const seen = Object.keys(restored.cards).length;
          if (!confirm(`Replace progress on this phone with the backup (${seen} cards seen)?`)) return;
          update(restored);
          repick(restored, session);
        }}
      />
    );
  }

  return (
    <div className="study">
      <header className="topbar">
        <select className="kind" value={kind} onChange={(e) => changeKind(e.target.value as Kind | "all")} aria-label="Cards">
          <option value="all">All cards</option>
          {KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
        </select>
        <span className="today">{reviewsToday(progress, new Date())} today</span>
        {undoable.length > 0 && <button className="undo" onClick={undo}>↶ Undo</button>}
        <button className="ghost" onClick={() => setView("menu")} aria-label="Menu">☰</button>
      </header>

      {saveError && <p className="error">Couldn't save progress: {saveError}</p>}

      <main className="stage">
        {pick ? (
          <CardView
            key={pick.card.id + session.recent.length}
            pick={pick}
            outcome={outcome}
            flagged={pick.card.id in progress.flags}
            onOutcome={setOutcome}
            onFlag={() => update(toggleFlag(progress, pick.card.id, new Date()))}
          />
        ) : (
          <CaughtUp
            moreAvailable={cards.some((c) => !(c.id in progress.cards))}
            onMore={() => {
              const next = addExtraNew(progress, EXTRA_NEW, new Date());
              update(next);
              repick(next, session);
            }}
          />
        )}
      </main>

      {pick && outcome && (
        <footer className="actions">
          <button className={`missed ${outcome.right ? "" : "suggested"}`} onClick={() => answer(false)}>Missed</button>
          <button className={`got ${outcome.right ? "suggested" : ""}`} onClick={() => answer(true)}>Got it</button>
        </footer>
      )}
    </div>
  );
}

function CaughtUp({ moreAvailable, onMore }: { moreAvailable: boolean; onMore: () => void }) {
  return (
    <div className="caught-up">
      <p className="card-front">That's everything for now.</p>
      <p className="muted">Cards you've seen will come back when they're due.</p>
      {moreAvailable && <button onClick={onMore}>Learn {EXTRA_NEW} more</button>}
      <NewGames />
    </div>
  );
}

function BrokenStorage({ message }: { message: string }) {
  const raw = rawStoredProgress();
  return (
    <div className="menu">
      <h1>Saved progress couldn't be read</h1>
      <p className="error">{message}</p>
      <p>Nothing has been deleted. Save the raw data first, then start fresh if you want.</p>
      <div className="row">
        {raw && <button onClick={() => void exportBackup(raw, new Date())}>Save raw data</button>}
        <button
          onClick={() => {
            if (confirm("Delete the unreadable progress and start fresh?")) {
              clearStoredProgress();
              location.reload();
            }
          }}
        >
          Start fresh
        </button>
      </div>
    </div>
  );
}
