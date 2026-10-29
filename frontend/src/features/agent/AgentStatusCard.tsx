import { Bot } from "lucide-react";
import { cn } from "@/lib/cn";
import { useAgentStatus } from "./api";
import { MockBadge } from "./RunStatusBadge";

/** Compact agent status for the sidebar: on/off, the real model name, mock + sending mode. */
export function AgentStatusCard() {
  const status = useAgentStatus();
  const data = status.data;
  if (status.isError) {
    return <p className="px-1 text-xs text-danger">Agent status unavailable</p>;
  }
  if (!data) return <div className="skeleton h-16 w-full rounded-xl" aria-hidden />;

  return (
    <section
      aria-label="Sales agent status"
      className="space-y-2 rounded-xl border border-border bg-surface-strong/70 p-3 text-xs shadow-soft"
    >
      <p className="flex items-center gap-2 font-semibold text-fg">
        <Bot className="size-4 text-brand-fg" aria-hidden />
        Sales agent
        <span
          className={cn(
            "ml-auto rounded-full px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide",
            data.enabled
              ? "bg-emerald-100 text-emerald-900 dark:bg-emerald-400/15 dark:text-emerald-200"
              : "bg-surface-muted text-fg-muted",
          )}
        >
          {data.enabled ? "On" : "Off"}
        </span>
      </p>
      <p className="truncate font-mono text-fg-muted" title={data.model}>
        {data.model}
      </p>
      {data.is_mock ? <MockBadge /> : null}
      <p className="text-fg-subtle">
        Instagram:{" "}
        <span
          className={cn("font-medium", data.instagram_sending === "live" ? "text-success" : "text-fg-muted")}
        >
          {data.instagram_sending}
        </span>
        {" · "}Payments: <span className="font-medium text-fg-muted">{data.payments.replace(/_/g, " ")}</span>
      </p>
    </section>
  );
}
