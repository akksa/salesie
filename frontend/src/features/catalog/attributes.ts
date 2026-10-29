import type { Attributes, JsonValue } from "@/api/types";

/** One editable key/value row. `original` keeps non-string JSON values intact if left unedited. */
export interface AttributeRow {
  rowId: string;
  key: string;
  value: string;
  original?: JsonValue;
}

let rowCounter = 0;
export function newRowId(): string {
  rowCounter += 1;
  return `attr-${rowCounter}`;
}

function valueToText(value: JsonValue): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

export function rowsFromAttributes(attributes: Attributes): AttributeRow[] {
  return Object.entries(attributes).map(([key, value]) => ({
    rowId: newRowId(),
    key,
    value: valueToText(value),
    original: value,
  }));
}

export type AttributesResult = { ok: true; value: Attributes } | { ok: false; error: string };

/**
 * Rows -> attributes object. Blank rows are dropped; edited values are saved as
 * strings; untouched non-string values (numbers, lists…) keep their original type.
 */
export function attributesFromRows(rows: AttributeRow[]): AttributesResult {
  const filled = rows.filter((row) => row.key.trim() !== "" || row.value.trim() !== "");
  const missingKey = filled.find((row) => row.key.trim() === "");
  if (missingKey) return { ok: false, error: `Give the value "${missingKey.value.trim()}" a name` };

  const keys = filled.map((row) => row.key.trim());
  const duplicate = keys.find((key, index) => keys.indexOf(key) !== index);
  if (duplicate) return { ok: false, error: `"${duplicate}" is listed twice` };

  const entries = filled.map((row): [string, JsonValue] => {
    const unchanged = row.original !== undefined && valueToText(row.original) === row.value;
    return [row.key.trim(), unchanged && row.original !== undefined ? row.original : row.value.trim()];
  });
  return { ok: true, value: Object.fromEntries(entries) };
}

export function sameAttributes(a: Attributes, b: Attributes): boolean {
  return JSON.stringify(Object.entries(a)) === JSON.stringify(Object.entries(b));
}
