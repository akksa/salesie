import type { Author, MessageOut } from "@/api/types";
import { previewWithoutUrls } from "@/lib/linkify";

export function authorLabel(author: Author, contactName: string): string {
  if (author === "agent") return "Salesie agent";
  if (author === "owner") return "You";
  return contactName;
}

/** Preview prefix by author. One spelling everywhere (inbox list, pipeline cards). */
export const AUTHOR_PREFIX: Record<Author, string> = { contact: "", agent: "Salesie:", owner: "You:" };

export function previewText(message: MessageOut | null): string {
  if (!message) return "No messages yet";
  const body = message.text?.trim() ? previewWithoutUrls(message.text) : "Attachment or unsupported message";
  const prefix = AUTHOR_PREFIX[message.author];
  return prefix ? `${prefix} ${body}` : body;
}

export function sameDay(a: string, b: string): boolean {
  return new Date(a).toDateString() === new Date(b).toDateString();
}
