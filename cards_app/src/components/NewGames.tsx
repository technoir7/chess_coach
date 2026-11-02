import { useEffect, useState } from "react";
import { deck } from "../deck";
import { loadNewVersion, message, startUpdate, updateStatus, type UpdateStatus } from "../newGames";

const POLL_MS = 3000;

export function NewGames() {
  const [status, setStatus] = useState<UpdateStatus>({ state: "idle" });
  const [error, setError] = useState<string | null>(null);

  // Pick up a run already going, say one started before the screen locked.
  // Offline, this stays quiet: pressing the button reports it.
  useEffect(() => {
    updateStatus().then((s) => s.state === "running" && setStatus(s), () => {});
  }, []);

  useEffect(() => {
    if (status.state !== "running") return;
    const timer = setInterval(async () => {
      try {
        const next = await updateStatus();
        if (next.state === "running") return;
        setStatus(next);
        if ((next.state === "done" || next.state === "partial") && next.cards > deck.length) await loadNewVersion();
      } catch {
        // A dropped poll (signal on a bus) isn't the update failing; the next one asks again.
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [status.state]);

  const press = async () => {
    setError(null);
    try {
      setStatus(await startUpdate());
    } catch {
      setError("Can't reach the Mac. It needs to be awake, with Tailscale on.");
    }
  };

  const text = error ?? message(status, deck.length);
  return (
    <div className="new-games">
      <button onClick={press} disabled={status.state === "running"}>
        {status.state === "running" ? "Getting new games…" : "Get new games"}
      </button>
      {text && <p className="muted small">{text}</p>}
    </div>
  );
}
