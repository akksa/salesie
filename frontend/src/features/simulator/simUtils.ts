import type { SimulationResult, WebhookEventOut } from "@/api/types";

/** Mirrors `InstagramUsername` in schemas.py. */
export const USERNAME_PATTERN = /^[A-Za-z0-9._]{1,30}$/;

const FIRST = ["linen", "boho", "studio", "silver", "sunny", "velvet", "thrift", "urban", "tiny", "cozy"];
const SECOND = ["lover", "hunter", "closet", "days", "corner", "finds", "edit", "club", "diaries", "mood"];

export function randomUsername(): string {
  const pick = (words: string[]) => words[Math.floor(Math.random() * words.length)] ?? words[0] ?? "user";
  return `${pick(FIRST)}.${pick(SECOND)}${Math.floor(Math.random() * 90) + 10}`;
}

export function validateUsername(value: string): string | undefined {
  const trimmed = value.trim().replace(/^@/, "");
  if (!trimmed) return "Pick a username";
  if (!USERNAME_PATTERN.test(trimmed)) return "Letters, numbers, dots and underscores only (max 30)";
  return undefined;
}

export function cleanUsername(value: string): string {
  return value.trim().replace(/^@/, "");
}

/**
 * Prefer the live (polled) status/error of an event, e.g. after a replay, while
 * keeping the contact/conversation ids that only the simulator response carries.
 */
export function liveEvent(events: WebhookEventOut[] | undefined, result: SimulationResult): SimulationResult {
  const live = events?.find((e) => e.id === result.id);
  return live
    ? { ...result, status: live.status, error: live.error, processed_at: live.processed_at }
    : result;
}

export const COMMENT_IDEAS = [
  "Price?",
  "Is this still available?",
  "Do you ship nationwide?",
  "Need 2 of these",
];
export const DM_IDEAS = [
  "Hi! How much is the dress?",
  "Can I pay on delivery?",
  "Do you have it in another colour?",
];
