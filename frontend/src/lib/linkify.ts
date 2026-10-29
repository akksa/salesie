import { safeHttpUrl } from "./url";

export type TextSegment = { kind: "text"; text: string } | { kind: "link"; text: string; href: string };

const URL_PATTERN = /https?:\/\/[^\s<>"']+/gi;
// Punctuation that usually ends a sentence rather than the URL ("pay here: https://x/pay/abc.").
const TRAILING = /[.,;:!?)\]}]+$/;

/**
 * Splits untrusted text into plain-text and link segments. Only absolute http(s)
 * URLs become links; everything else stays text (rendered by React, never as HTML).
 */
export function linkify(text: string): TextSegment[] {
  const segments: TextSegment[] = [];
  let cursor = 0;
  for (const match of text.matchAll(URL_PATTERN)) {
    const start = match.index ?? 0;
    const raw = match[0];
    const url = raw.replace(TRAILING, "");
    const href = safeHttpUrl(url);
    if (!href) continue;
    if (start > cursor) segments.push({ kind: "text", text: text.slice(cursor, start) });
    segments.push({ kind: "link", text: url, href });
    cursor = start + url.length;
  }
  if (cursor < text.length) segments.push({ kind: "text", text: text.slice(cursor) });
  return segments;
}

/** Hosted checkout links look like `{PUBLIC_BASE_URL}/pay/{token}`. */
function isPaymentLink(href: string): boolean {
  try {
    return /^\/pay\/[^/]+\/?$/.test(new URL(href).pathname);
  } catch {
    return false;
  }
}

export function paymentLinks(text: string | null): string[] {
  if (!text) return [];
  return linkify(text).flatMap((s) => (s.kind === "link" && isPaymentLink(s.href) ? [s.href] : []));
}
