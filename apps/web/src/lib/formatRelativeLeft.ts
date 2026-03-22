/** Human-readable "Left … ago" from an ISO timestamp (UTC). */
export function formatLeftAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "Unknown";
  const now = Date.now();
  const sec = Math.floor((now - then) / 1000);
  if (sec < 60) return "Left just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `Left ${min} min ago`;
  const hr = Math.floor(min / 60);
  if (hr < 48) return `Left ${hr} hour${hr === 1 ? "" : "s"} ago`;
  const day = Math.floor(hr / 24);
  if (day < 14) return `Left ${day} day${day === 1 ? "" : "s"} ago`;
  const week = Math.floor(day / 7);
  if (week < 8) return `Left ${week} week${week === 1 ? "" : "s"} ago`;
  const month = Math.floor(day / 30);
  const m = Math.max(1, month);
  return `Left ${m} month${m === 1 ? "" : "s"} ago`;
}
