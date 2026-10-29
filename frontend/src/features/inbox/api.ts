import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { LIVE_POLL_MS, queryKeys } from "@/api/queryKeys";
import type { ConversationDetail, ConversationListItem } from "@/api/types";

export function useConversations() {
  return useQuery({
    queryKey: queryKeys.conversations,
    queryFn: () => api.get<ConversationListItem[]>("/api/conversations"),
    refetchInterval: LIVE_POLL_MS,
  });
}

export function useConversation(id: number | null) {
  return useQuery({
    queryKey: queryKeys.conversation(id ?? 0),
    queryFn: () => api.get<ConversationDetail>(`/api/conversations/${id}`),
    refetchInterval: LIVE_POLL_MS,
    enabled: id !== null && Number.isInteger(id) && id > 0,
  });
}
