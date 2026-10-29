import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import type { AgentRunOut, ContactDetail, ConversationDetail, PostOut, SimulationResult } from "@/api/types";
import { useContact, useContacts } from "@/features/contacts/api";
import { useConversation, useConversations } from "@/features/inbox/api";
import { useSimulateComment, useSimulateDm } from "../api";
import { findShopper, instagramConversation, type PendingSend } from "./phoneThread";

interface Linked {
  username: string;
  contactId: number | null;
  conversationId: number | null;
}

export interface SendInput {
  kind: "dm" | "comment";
  username: string;
  text: string;
  post: PostOut | undefined;
}

/**
 * The shopper's side of the demo: resolves which contact/conversation the username
 * maps to (preferring ids returned by the simulator), sends DMs/comments, and keeps
 * a pending bubble + "typing" state until the agent's reply has been fetched.
 */
export function useShopperSession(
  username: string,
  onSent: (result: SimulationResult, input: SendInput) => void,
) {
  const queryClient = useQueryClient();
  const contacts = useContacts();
  const conversations = useConversations();
  const [linked, setLinked] = useState<Linked | null>(null);
  const [pending, setPending] = useState<PendingSend | null>(null);
  const [lastRuns, setLastRuns] = useState<AgentRunOut[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const comment = useSimulateComment();
  const dm = useSimulateDm();

  const own = linked?.username.toLowerCase() === username.toLowerCase() ? linked : null;
  const contactId = own?.contactId ?? findShopper(contacts.data, username)?.id ?? null;
  const conversationId =
    own?.conversationId ??
    (contactId ? (instagramConversation(conversations.data, contactId)?.id ?? null) : null);
  const conversation = useConversation(conversationId);
  const contact = useContact(contactId ?? 0);

  async function send(input: SendInput): Promise<boolean> {
    setError(null);
    setLastRuns(null);
    setPending({ kind: input.kind, text: input.text, post: input.post, at: new Date().toISOString() });
    try {
      const result =
        input.kind === "dm"
          ? await dm.mutateAsync({ username: input.username, text: input.text })
          : await comment.mutateAsync({
              post_id: input.post?.id ?? 0,
              username: input.username,
              text: input.text,
            });
      setLinked({
        username: input.username,
        contactId: result.contact_id,
        conversationId: result.conversation_id,
      });
      setLastRuns(result.agent_runs);
      onSent(result, input);
      // Fill the cache before dropping the pending bubble, so the reply appears without a flash.
      const conversationId = result.conversation_id;
      const contactId = result.contact_id;
      await Promise.all([
        conversationId
          ? queryClient.fetchQuery({
              queryKey: queryKeys.conversation(conversationId),
              queryFn: () => api.get<ConversationDetail>(`/api/conversations/${conversationId}`),
            })
          : null,
        contactId
          ? queryClient.fetchQuery({
              queryKey: queryKeys.contact(contactId),
              queryFn: () => api.get<ContactDetail>(`/api/contacts/${contactId}`),
            })
          : null,
      ]).catch(() => undefined); // polling retries; the send itself already succeeded
      return true;
    } catch (caught) {
      setError(caught);
      return false;
    } finally {
      setPending(null);
    }
  }

  const reset = () => {
    setLinked(null);
    setLastRuns(null);
    setError(null);
  };

  return { conversation, contact, pending, lastRuns, error, sending: pending !== null, send, reset };
}
