/**
 * Returns the URL only if it is an absolute http(s) URL. Used before putting any
 * server-provided (and ultimately user-provided) URL into href/src.
 */
export function safeHttpUrl(value: string | null | undefined): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : undefined;
  } catch {
    return undefined;
  }
}

export function isHttpUrl(value: string): boolean {
  return safeHttpUrl(value) !== undefined;
}
