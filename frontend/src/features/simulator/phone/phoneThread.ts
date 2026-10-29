import type { ContactListItem, ConversationListItem, EngagementOut, MessageOut, PostOut } from "@/api/types";

/** A line in the shopper's phone. "shopper" renders on the right, "shop" (Salesie) on the left. */
export type PhoneItem =
  | {
      kind: "message";
      key: string;
      at: string;
      side: "shopper" | "shop";
      text: string | null;
      pending?: boolean;
    }
  | {
      kind: "comment";
      key: string;
      at: string;
      text: string | null;
      post: PostOut | undefined;
      pending?: boolean;
    };

export interface PendingSend {
  kind: "dm" | "comment";
  text: string;
  post: PostOut | undefined;
  at: string;
}

export function buildPhoneItems(
  messages: MessageOut[] | undefined,
  engagements: EngagementOut[] | undefined,
  postsById: ReadonlyMap<number, PostOut>,
  pending: PendingSend | null,
): PhoneItem[] {
  const fromMessages: PhoneItem[] = (messages ?? []).map((m) => ({
    kind: "message",
    key: `m${m.id}`,
    at: m.sent_at,
    side: m.direction === "inbound" ? "shopper" : "shop",
    text: m.text,
  }));
  const fromComments: PhoneItem[] = (engagements ?? [])
    .filter((e) => e.kind === "comment" && e.channel === "instagram")
    .map((e) => ({
      kind: "comment",
      key: `e${e.id}`,
      at: e.occurred_at,
      text: e.text,
      post: e.post_id === null ? undefined : postsById.get(e.post_id),
    }));
  const items = [...fromComments, ...fromMessages].sort(
    (a, b) => new Date(a.at).getTime() - new Date(b.at).getTime(),
  );
  if (!pending) return items;
  const pendingItem: PhoneItem =
    pending.kind === "dm"
      ? {
          kind: "message",
          key: "pending",
          at: pending.at,
          side: "shopper",
          text: pending.text,
          pending: true,
        }
      : {
          kind: "comment",
          key: "pending",
          at: pending.at,
          text: pending.text,
          post: pending.post,
          pending: true,
        };
  return [...items, pendingItem];
}

/** Existing Instagram shopper by username (case-insensitive). */
export function findShopper(contacts: ContactListItem[] | undefined, username: string) {
  const needle = username.trim().replace(/^@/, "").toLowerCase();
  if (!needle) return undefined;
  return contacts?.find((c) =>
    c.identities.some((i) => i.channel === "instagram" && i.username?.toLowerCase() === needle),
  );
}

export function instagramConversation(conversations: ConversationListItem[] | undefined, contactId: number) {
  return conversations?.find((c) => c.contact_id === contactId && c.channel === "instagram");
}

export function knownUsernames(contacts: ContactListItem[] | undefined): string[] {
  const names = (contacts ?? []).flatMap((c) =>
    c.identities.flatMap((i) => (i.channel === "instagram" && i.username ? [i.username] : [])),
  );
  return [...new Set(names)].sort((a, b) => a.localeCompare(b));
}
