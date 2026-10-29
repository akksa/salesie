import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { LIVE_POLL_MS, queryKeys } from "@/api/queryKeys";
import type { ContactDetail, ContactListItem } from "@/api/types";

export function useContacts() {
  return useQuery({
    queryKey: queryKeys.contacts,
    queryFn: () => api.get<ContactListItem[]>("/api/contacts"),
    refetchInterval: LIVE_POLL_MS,
  });
}

export function useContact(id: number) {
  return useQuery({
    queryKey: queryKeys.contact(id),
    queryFn: () => api.get<ContactDetail>(`/api/contacts/${id}`),
    refetchInterval: LIVE_POLL_MS,
    enabled: Number.isInteger(id) && id > 0,
  });
}
