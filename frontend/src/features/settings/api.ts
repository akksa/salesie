import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import type { AppConfig, BusinessOut, BusinessUpdate } from "@/api/types";

export function useAppConfig() {
  return useQuery({
    queryKey: queryKeys.appConfig,
    queryFn: () => api.get<AppConfig>("/api/app-config"),
    staleTime: 5 * 60_000,
  });
}

export function useBusiness() {
  return useQuery({
    queryKey: queryKeys.business,
    queryFn: () => api.get<BusinessOut>("/api/business"),
    staleTime: 60_000,
  });
}

/** Business currency for money formatting; falls back to USD until the business loads. */
export function useCurrency(): string {
  return useBusiness().data?.currency ?? "USD";
}

export function useUpdateBusiness() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: BusinessUpdate) => api.patch<BusinessOut>("/api/business", body),
    onSuccess: (business) => {
      queryClient.setQueryData(queryKeys.business, business);
    },
  });
}
