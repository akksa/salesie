import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { LIVE_POLL_MS, queryKeys } from "@/api/queryKeys";
import type { AgentRunOut, AgentStatusOut, ConversationDetail, ConversationListItem } from "@/api/types";

export function useAgentStatus() {
  return useQuery({
    queryKey: queryKeys.agentStatus,
    queryFn: () => api.get<AgentStatusOut>("/api/agent"),
    staleTime: 60_000,
  });
}

/** Runs for the conversation's contact, newest first (the server scopes them by contact). */
export function useAgentRuns(conversationId: number | null) {
  return useQuery({
    queryKey: queryKeys.agentRuns(conversationId ?? 0),
    queryFn: () => api.get<AgentRunOut[]>(`/api/conversations/${conversationId}/agent-runs`),
    refetchInterval: LIVE_POLL_MS,
    enabled: conversationId !== null && conversationId > 0,
  });
}

/** Pause the agent to take a chat over, or hand it back. */
export function useSetAgentPaused(conversationId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (agentPaused: boolean) =>
      api.patch<ConversationListItem>(`/api/conversations/${conversationId}`, { agent_paused: agentPaused }),
    onSuccess: (updated) => {
      queryClient.setQueryData<ConversationDetail>(queryKeys.conversation(conversationId), (old) =>
        old ? { ...old, ...updated, messages: old.messages } : old,
      );
      queryClient.setQueryData<ConversationListItem[]>(queryKeys.conversations, (old) =>
        old?.map((c) => (c.id === updated.id ? updated : c)),
      );
      void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
      void queryClient.invalidateQueries({ queryKey: queryKeys.contact(updated.contact_id) });
    },
  });
}
