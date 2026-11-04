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

/**
 * Splits checkout links out of a message so they can be shown as an "Open checkout"
 * button instead of a raw URL. Other URLs stay in the text (rendered as links).
 */
export function splitPaymentLinks(text: string): { text: string; links: string[] } {
  const links: string[] = [];
  const kept = linkify(text)
    .map((segment) => {
      if (segment.kind === "link" && isPaymentLink(segment.href)) {
        links.push(segment.href);
        return "";
      }
      return segment.text;
    })
    .join("");
  const cleaned = kept
    .replace(/[ \t]+\n/g, "\n")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/[ \t]+([.,;!?)])/g, "$1") // punctuation that followed the removed URL
    .replace(/:\s*\.(\s|$)/g, ":$1") // "Pay here: ." -> "Pay here:"
    .trim();
  return { text: cleaned, links: [...new Set(links)] };
}

/** One-line preview with URLs replaced by a label, for lists and cards. */
export function previewWithoutUrls(text: string): string {
  return linkify(text)
    .map((segment) => {
      if (segment.kind !== "link") return segment.text;
      return isPaymentLink(segment.href) ? "🔗 Checkout link" : "🔗 Link";
    })
    .join("")
    .replace(/\s+/g, " ")
    .trim();
}
