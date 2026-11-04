import { useIsMutating, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { LIVE_POLL_MS, queryKeys } from "@/api/queryKeys";
import type { ConversationDetail, ConversationListItem, MessageOut } from "@/api/types";

export function useConversations() {
  return useQuery({
    queryKey: queryKeys.conversations,
    queryFn: () => api.get<ConversationListItem[]>("/api/conversations"),
    refetchInterval: LIVE_POLL_MS,
  });
}

const sendKey = (conversationId: number) => ["send-owner-message", conversationId] as const;

export function useConversation(id: number | null) {
  // Don't let a poll replace the optimistic owner message while it's being sent.
  const sending = useIsMutating({ mutationKey: sendKey(id ?? 0) }) > 0;
  return useQuery({
    queryKey: queryKeys.conversation(id ?? 0),
    queryFn: () => api.get<ConversationDetail>(`/api/conversations/${id}`),
    refetchInterval: sending ? false : LIVE_POLL_MS,
    enabled: id !== null && Number.isInteger(id) && id > 0,
  });
}

/**
 * Owner reply. Shown optimistically (negative temporary id), rolled back on error.
 * The server pauses the agent on this chat, so list/pipeline data is refreshed after.
 */
export function useSendOwnerMessage(conversationId: number) {
  const queryClient = useQueryClient();
  const key = queryKeys.conversation(conversationId);
  return useMutation({
    mutationKey: sendKey(conversationId),
    mutationFn: (text: string) =>
      api.post<MessageOut>(`/api/conversations/${conversationId}/messages`, { text }),
    onMutate: async (text) => {
      await queryClient.cancelQueries({ queryKey: key, exact: true });
      const tempId = -Date.now();
      const temp: MessageOut = {
        id: tempId,
        direction: "outbound",
        author: "owner",
        text,
        sent_at: new Date().toISOString(),
        agent_run_id: null,
      };
      queryClient.setQueryData<ConversationDetail>(key, (old) =>
        old ? { ...old, messages: [...old.messages, temp] } : old,
      );
      return { tempId };
    },
    onError: (_error, _text, context) => {
      queryClient.setQueryData<ConversationDetail>(key, (old) =>
        old ? { ...old, messages: old.messages.filter((m) => m.id !== context?.tempId) } : old,
      );
    },
    onSuccess: (message, _text, context) => {
      queryClient.setQueryData<ConversationDetail>(key, (old) =>
        old ? { ...old, messages: old.messages.map((m) => (m.id === context?.tempId ? message : m)) } : old,
      );
    },
    onSettled: () => {
      for (const k of [key, queryKeys.conversations, queryKeys.pipeline, queryKeys.contacts]) {
        void queryClient.invalidateQueries({ queryKey: k });
      }
    },
  });
}
