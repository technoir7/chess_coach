// A study day rolls over at 4am, so a session that runs past midnight
// counts toward the evening it started in.
const ROLLOVER_HOURS = 4;

export function studyDay(now: Date): string {
  // Calendar arithmetic, not "subtract 4 hours of milliseconds": the latter
  // lands on the wrong date on the night the clocks change.
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - (now.getHours() < ROLLOVER_HOURS ? 1 : 0));
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
