/** Fixed global levels so colors mean the same for every player. */
export type ActivityLevel = 0 | 1 | 2 | 3 | 4;

export const HEATMAP_DAY_COUNT = 90;

/** Legend / tooltip copy — keep in sync with `attackCountToLevel`. */
export const LEVEL_LABELS = ["0", "1–4", "5–9", "10–19", "20+"] as const;

/**
 * Tailwind-friendly classes; shared by heatmap cells and legend squares.
 * Level 0 = no attacks; 1–4 ramp through Radix accent scale.
 */
export const HEATMAP_LEVEL_CELL_CLASSES: readonly string[] = [
  "rounded-sm bg-[var(--gray-4)] border border-[var(--gray-6)]",
  "rounded-sm bg-[var(--accent-4)]",
  "rounded-sm bg-[var(--accent-6)]",
  "rounded-sm bg-[var(--accent-8)]",
  "rounded-sm bg-[var(--accent-9)]",
];

export function attackCountToLevel(count: number): ActivityLevel {
  if (count <= 0) return 0;
  if (count <= 4) return 1;
  if (count <= 9) return 2;
  if (count <= 19) return 3;
  return 4;
}

function formatAttackSpanDaysFromFirstMs(firstMs: number): string | null {
  const days = (Date.now() - firstMs) / 86_400_000;
  if (!Number.isFinite(days) || days < 0) return null;
  if (days < 0.1) return "<0.1";
  if (days < 10) return days.toFixed(1);
  return days.toFixed(0);
}

/** Days from earliest attack in the list to now (browser clock). Used for profile chart subtitle. */
export function formatAttackHistorySpanDays(attacks: { attacked_at: string }[]): string | null {
  if (attacks.length === 0) return null;
  const first = Math.min(...attacks.map((a) => new Date(a.attacked_at).getTime()));
  if (Number.isNaN(first)) return null;
  return formatAttackSpanDaysFromFirstMs(first);
}

/**
 * Same numeric rules as formatAttackHistorySpanDays; use with earliest attack ISO from the API 7d window.
 */
export function formatAttackSpanDaysFromIso(earliestIso: string | null | undefined): string | null {
  if (earliestIso == null || earliestIso === "") return null;
  const first = new Date(earliestIso).getTime();
  if (Number.isNaN(first)) return null;
  return formatAttackSpanDaysFromFirstMs(first);
}

export function localDateKey(d: Date): string {
  const y = d.getFullYear();
  const m = d.getMonth() + 1;
  const day = d.getDate();
  return `${y}-${String(m).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function startOfLocalDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function addLocalDays(baseStart: Date, dayOffset: number): Date {
  const x = new Date(baseStart);
  x.setDate(x.getDate() + dayOffset);
  return startOfLocalDay(x);
}

/** Inclusive range: `rangeStart` + 0 .. `dayCount - 1` (local calendar days). */
export function getHeatmapRangeStart(dayCount: number = HEATMAP_DAY_COUNT): Date {
  const today = startOfLocalDay(new Date());
  const start = new Date(today);
  start.setDate(start.getDate() - (dayCount - 1));
  return startOfLocalDay(start);
}

/** Count attacks per local calendar day (YYYY-MM-DD) for the last `dayCount` days including today. */
export function buildDailyCounts(
  attacks: { attacked_at: string }[],
  dayCount: number = HEATMAP_DAY_COUNT,
): Map<string, number> {
  const rangeStart = getHeatmapRangeStart(dayCount);
  const counts = new Map<string, number>();

  for (let i = 0; i < dayCount; i++) {
    counts.set(localDateKey(addLocalDays(rangeStart, i)), 0);
  }

  for (const a of attacks) {
    const key = localDateKey(new Date(a.attacked_at));
    const n = counts.get(key);
    if (n !== undefined) counts.set(key, n + 1);
  }

  return counts;
}

export interface HeatmapCellModel {
  dayIndex: number;
  dateKey: string;
  count: number;
  level: ActivityLevel;
}

export interface HeatmapGridModel {
  rangeStart: Date;
  /** Sunday = 0 .. Saturday = 6 for `rangeStart`. */
  firstDayOfWeek: number;
  columnCount: number;
  /** Column-major order: for each column c, rows 0..6 top to bottom (Sun..Sat). */
  cells: (HeatmapCellModel | null)[][];
  /** One label per column (month abbr) or null. */
  monthLabels: (string | null)[];
}

export function buildHeatmapGrid(
  dailyCounts: Map<string, number>,
  dayCount: number = HEATMAP_DAY_COUNT,
): HeatmapGridModel {
  const rangeStart = getHeatmapRangeStart(dayCount);
  const firstDayOfWeek = rangeStart.getDay();
  const columnCount = Math.ceil((firstDayOfWeek + dayCount) / 7);

  const cells: (HeatmapCellModel | null)[][] = [];
  for (let c = 0; c < columnCount; c++) {
    const col: (HeatmapCellModel | null)[] = [];
    for (let r = 0; r < 7; r++) {
      const dayIndex = c * 7 + r - firstDayOfWeek;
      if (dayIndex < 0 || dayIndex >= dayCount) {
        col.push(null);
        continue;
      }
      const d = addLocalDays(rangeStart, dayIndex);
      const dateKey = localDateKey(d);
      const count = dailyCounts.get(dateKey) ?? 0;
      const level = attackCountToLevel(count);
      col.push({ dayIndex, dateKey, count, level });
    }
    cells.push(col);
  }

  const monthFormatter = new Intl.DateTimeFormat(undefined, { month: "short" });
  const monthLabels: (string | null)[] = [];
  for (let c = 0; c < columnCount; c++) {
    let label: string | null = null;
    for (let r = 0; r < 7; r++) {
      const dayIndex = c * 7 + r - firstDayOfWeek;
      if (dayIndex < 0 || dayIndex >= dayCount) continue;
      const d = addLocalDays(rangeStart, dayIndex);
      if (d.getDate() === 1) {
        label = monthFormatter.format(d);
        break;
      }
    }
    monthLabels.push(label);
  }

  return { rangeStart, firstDayOfWeek, columnCount, cells, monthLabels };
}

/** Keep attacks from the last `days` local calendar days (including today). */
export function filterAttacksToLastLocalDays(
  attacks: { attacked_at: string }[],
  days: number,
): { attacked_at: string }[] {
  const rangeStart = getHeatmapRangeStart(days);
  const startMs = rangeStart.getTime();
  const todayStart = startOfLocalDay(new Date());
  const tomorrowStart = new Date(todayStart);
  tomorrowStart.setDate(tomorrowStart.getDate() + 1);
  return attacks.filter((a) => {
    const t = new Date(a.attacked_at).getTime();
    return t >= startMs && t < tomorrowStart.getTime();
  });
}
