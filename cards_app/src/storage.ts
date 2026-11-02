// Device storage and backup files: the only module that touches localStorage
// or the file system. Progress is small (a few hundred KB at most), so
// localStorage is enough.
import { emptyProgress, parseProgress, type Progress } from "./study/progress";
import { studyDay } from "./study/day";

const KEY = "chess-cards.progress";

/** Throws if stored data exists but is unreadable, so it is never silently replaced. */
export function loadProgress(): Progress {
  const raw = localStorage.getItem(KEY);
  return raw === null ? emptyProgress() : parseProgress(JSON.parse(raw));
}

export function rawStoredProgress(): string | null {
  return localStorage.getItem(KEY);
}

export function saveProgress(p: Progress): void {
  localStorage.setItem(KEY, JSON.stringify(p));
}

export function clearStoredProgress(): void {
  localStorage.removeItem(KEY);
}

/** Ask the browser not to evict our data under storage pressure. Best effort. */
export async function requestPersistence(): Promise<boolean> {
  return (await navigator.storage?.persist?.()) ?? false;
}

/** Hand the backup to the share sheet (Save to Files, AirDrop) or download it. */
export async function exportBackup(text: string, now: Date): Promise<void> {
  const name = `chess-cards-backup-${studyDay(now)}.json`;
  const file = new File([text], name, { type: "application/json" });
  if (navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: name });
      return;
    } catch (e) {
      // Closing the share sheet is a choice, not a failure.
      if (e instanceof DOMException && e.name === "AbortError") return;
      throw e;
    }
  }
  const url = URL.createObjectURL(file);
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  URL.revokeObjectURL(url);
}

export async function readBackupFile(file: File): Promise<Progress> {
  return parseProgress(JSON.parse(await file.text()));
}
