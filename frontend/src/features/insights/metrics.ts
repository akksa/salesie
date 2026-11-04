/** Pure display helpers for the insights page. */

const percentFormatter = new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 0 });
const oneDecimal = new Intl.NumberFormat(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const integer = new Intl.NumberFormat();

export function formatPercent(ratio: number | null | undefined): string {
  return ratio === null || ratio === undefined || !Number.isFinite(ratio)
    ? "—"
    : percentFormatter.format(ratio);
}

export function formatCount(value: number): string {
  return integer.format(value);
}

/** 0.04 → "< 0.1 s", 1.24 → "1.2 s", 75 → "1.3 min", 5400 → "1.5 h". */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return "—";
  if (seconds < 0.1) return `< ${oneDecimal.format(0.1)} s`;
  if (seconds < 60) return `${oneDecimal.format(seconds)} s`;
  if (seconds < 3600) return `${oneDecimal.format(seconds / 60)} min`;
  return `${oneDecimal.format(seconds / 3600)} h`;
}

/** Share of `value` in `max`, clamped to 0–100, for bar widths. */
export function barPercent(value: number, max: number): number {
  if (max <= 0 || value <= 0) return 0;
  return Math.min(100, Math.max(0, (value / max) * 100));
}

/** Fraction kept from the previous step; null for the first step or an empty previous step. */
export function keptFrom(previous: number | undefined, current: number): number | null {
  if (previous === undefined || previous <= 0) return null;
  return current / previous;
}
