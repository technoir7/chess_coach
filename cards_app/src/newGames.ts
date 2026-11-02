// "Get new games": asks the Mac (tools/serve_app.py) to run tools/update.py,
// then loads the rebuilt app once it has new cards.

export type UpdateStatus =
  | { state: "idle" }
  | { state: "running" }
  | { state: "done" | "partial" | "failed"; finished: string; cards: number };

const URL = "/api/update";

async function call(method: "GET" | "POST"): Promise<UpdateStatus> {
  const response = await fetch(URL, { method, cache: "no-store" });
  if (!response.ok) throw new Error(`the Mac answered ${response.status}`);
  return (await response.json()) as UpdateStatus;
}

export const startUpdate = () => call("POST");
export const updateStatus = () => call("GET");

/** What to tell the player, given the Mac's status and how many cards this phone has. */
export function message(status: UpdateStatus, cardsHere: number): string | null {
  if (status.state === "idle") return null;
  if (status.state === "running") {
    return "Getting your new games… This takes a few minutes. You can close the app and come back.";
  }
  if (status.state === "failed") return "The update failed. The log is on the Mac: cards_app/tools/update.log.";
  const added = status.cards - cardsHere;
  if (added <= 0) return "No new cards since last time.";
  const count = added === 1 ? "1 new card." : `${added} new cards.`;
  const loading = added === 1 ? "Loading it…" : "Loading them…";
  const missing = status.state === "partial"
    ? " Some have no commentary yet (likely Claude's usage limit); the next update adds it."
    : "";
  return `${count}${missing} ${loading}`;
}

/** Fetch the rebuilt app: the service worker swaps it in and reloads the page. */
export async function loadNewVersion(): Promise<void> {
  const registration = await navigator.serviceWorker?.getRegistration();
  await registration?.update();
  // If no new worker takes over (say, the browser kept the old one), reload anyway.
  setTimeout(() => location.reload(), 4000);
}
