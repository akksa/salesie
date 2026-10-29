import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { LIVE_POLL_MS, queryKeys } from "@/api/queryKeys";
import type { DealOut } from "@/api/types";

export function useDeals() {
  return useQuery({
    queryKey: queryKeys.deals,
    queryFn: () => api.get<DealOut[]>("/api/deals"),
    refetchInterval: LIVE_POLL_MS,
  });
}
