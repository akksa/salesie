/** Formatting helpers for money and time. Pure functions only. */

const FALLBACK_CURRENCY = "USD";

function currencyFormatter(currency: string): Intl.NumberFormat {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency });
  } catch {
    // Backend only checks ^[A-Z]{3}$, so a well-formed but unknown code is possible.
    return new Intl.NumberFormat(undefined, { style: "currency", currency: FALLBACK_CURRENCY });
  }
}

/** Number of minor-unit digits for a currency (USD 2, JPY 0, KWD 3). */
export function fractionDigits(currency: string): number {
  return currencyFormatter(currency).resolvedOptions().maximumFractionDigits ?? 2;
}

export function formatMoney(minor: number | null | undefined, currency: string): string | null {
  if (minor === null || minor === undefined) return null;
  const digits = fractionDigits(currency);
  return currencyFormatter(currency).format(minor / 10 ** digits);
}

/** Minor units -> editable major-unit string ("1250" -> "12.50"). */
export function minorToInput(minor: number | null, currency: string): string {
  if (minor === null) return "";
  const digits = fractionDigits(currency);
  return (minor / 10 ** digits).toFixed(digits);
}

export type ParsedPrice = { ok: true; value: number | null } | { ok: false; error: string };

/** Parses a major-unit price typed by the owner into integer minor units. */
export function parsePriceInput(raw: string, currency: string): ParsedPrice {
  const text = raw.trim().replace(/,/g, "");
  if (text === "") return { ok: true, value: null };
  const digits = fractionDigits(currency);
  const pattern = digits === 0 ? /^\d+$/ : new RegExp(`^\\d+(\\.\\d{1,${digits}})?$`);
  if (!pattern.test(text)) {
    return {
      ok: false,
      error: digits === 0 ? `Enter a whole number (${currency} has no decimals)` : `Enter a price like 12.50`,
    };
  }
  const [whole = "0", fraction = ""] = text.split(".");
  const minor = Number(whole) * 10 ** digits + Number(fraction.padEnd(digits, "0") || "0");
  if (!Number.isSafeInteger(minor) || minor > 2_147_483_647) {
    return { ok: false, error: "That price is too large" };
  }
  return { ok: true, value: minor };
}

const RELATIVE_UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 3600],
  ["month", 30 * 24 * 3600],
  ["week", 7 * 24 * 3600],
  ["day", 24 * 3600],
  ["hour", 3600],
  ["minute", 60],
];

const relativeFormatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto", style: "short" });
const absoluteFormatter = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
const timeFormatter = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });

function toDate(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatRelative(iso: string | null | undefined, now: number = Date.now()): string {
  const date = toDate(iso);
  if (!date) return "—";
  const seconds = Math.round((date.getTime() - now) / 1000);
  if (Math.abs(seconds) < 45) return "just now";
  for (const [unit, size] of RELATIVE_UNITS) {
    if (Math.abs(seconds) >= size) return relativeFormatter.format(Math.round(seconds / size), unit);
  }
  return relativeFormatter.format(Math.round(seconds / 60), "minute");
}

export function formatAbsolute(iso: string | null | undefined): string {
  const date = toDate(iso);
  return date ? absoluteFormatter.format(date) : "";
}

export function formatTime(iso: string | null | undefined): string {
  const date = toDate(iso);
  return date ? timeFormatter.format(date) : "";
}

export function initials(name: string): string {
  const parts = name
    .replace(/^@/, "")
    .split(/[\s._-]+/)
    .filter(Boolean);
  const letters = parts.slice(0, 2).map((p) => p[0]?.toUpperCase() ?? "");
  return letters.join("") || "?";
}

/** Stringifies an arbitrary JSON attribute value for display as a chip. */
export function attributeToText(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.map(attributeToText).join(", ");
  return JSON.stringify(value);
}
