import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { LIVE_POLL_MS, queryKeys } from "@/api/queryKeys";
import type {
  SimulatedCommentIn,
  SimulatedDirectMessageIn,
  SimulationResult,
  WebhookEventOut,
  WebhookStatus,
} from "@/api/types";

export function useWebhookEvents(status?: WebhookStatus) {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return useQuery({
    queryKey: queryKeys.webhookEvents(status),
    queryFn: () => api.get<WebhookEventOut[]>(`/api/webhook-events${query}`),
    refetchInterval: LIVE_POLL_MS,
  });
}

/** A simulated event can touch every live list, so refresh them all immediately. */
function useRefreshLiveData() {
  const queryClient = useQueryClient();
  return () => {
    for (const key of [
      queryKeys.webhookEventsAll,
      queryKeys.contacts,
      queryKeys.conversations,
      queryKeys.deals,
      queryKeys.posts,
    ]) {
      void queryClient.invalidateQueries({ queryKey: key });
    }
  };
}

export function useSimulateComment() {
  const refresh = useRefreshLiveData();
  return useMutation({
    mutationFn: (body: SimulatedCommentIn) =>
      api.post<SimulationResult>("/api/simulator/instagram/comment", body),
    onSettled: refresh,
  });
}

export function useSimulateDm() {
  const refresh = useRefreshLiveData();
  return useMutation({
    mutationFn: (body: SimulatedDirectMessageIn) =>
      api.post<SimulationResult>("/api/simulator/instagram/dm", body),
    onSettled: refresh,
  });
}

/** Re-runs a stored delivery (idempotent). Refreshes every live list since it may create CRM rows. */
export function useReplayWebhookEvent() {
  const refresh = useRefreshLiveData();
  return useMutation({
    mutationFn: (id: number) => api.post<WebhookEventOut>(`/api/webhook-events/${id}/replay`, {}),
    onSettled: refresh,
  });
}
