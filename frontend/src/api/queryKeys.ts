/** Central query keys so mutations can invalidate exactly what they change. */
export const queryKeys = {
  appConfig: ["app-config"] as const,
  business: ["business"] as const,
  products: ["products"] as const,
  posts: ["posts"] as const,
  contacts: ["contacts"] as const,
  contact: (id: number) => ["contacts", id] as const,
  conversations: ["conversations"] as const,
  conversation: (id: number) => ["conversations", id] as const,
  deals: ["deals"] as const,
  deal: (id: number) => ["deals", id] as const,
  pipeline: ["pipeline"] as const,
  insights: (days: number) => ["insights", days] as const,
  agentStatus: ["agent"] as const,
  agentRuns: (conversationId: number) => ["conversations", conversationId, "agent-runs"] as const,
  webhookEvents: (status?: string) => ["webhook-events", status ?? "all"] as const,
  webhookEventsAll: ["webhook-events"] as const,
};

/** Live data (CRM + webhook events) is polled so simulated events show up without a reload. */
export const LIVE_POLL_MS = 3000;
