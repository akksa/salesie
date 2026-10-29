import type { Author, MessageOut } from "@/api/types";

export function authorLabel(author: Author, contactName: string): string {
  if (author === "agent") return "Salesie agent";
  if (author === "owner") return "You";
  return contactName;
}

export function previewText(message: MessageOut | null, contactName: string): string {
  if (!message) return "No messages yet";
  const body = message.text?.trim() || "Attachment or unsupported message";
  return message.author === "contact" ? body : `${authorLabel(message.author, contactName)}: ${body}`;
}

export function sameDay(a: string, b: string): boolean {
  return new Date(a).toDateString() === new Date(b).toDateString();
}
