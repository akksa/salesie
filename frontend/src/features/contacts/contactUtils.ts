import type { Channel, ContactListItem, IdentityOut } from "@/api/types";

export function primaryUsername(identities: IdentityOut[]): string | null {
  return identities.find((identity) => identity.username)?.username ?? null;
}

export function contactChannels(identities: IdentityOut[]): Channel[] {
  return identities.map((identity) => identity.channel);
}

/** Case-insensitive match on display name and any handle. */
export function matchesSearch(contact: ContactListItem, query: string): boolean {
  const needle = query.trim().toLowerCase().replace(/^@/, "");
  if (!needle) return true;
  const haystack = [contact.display_name, ...contact.identities.map((i) => i.username ?? "")];
  return haystack.some((value) => value.toLowerCase().includes(needle));
}
