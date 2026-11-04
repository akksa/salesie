import { Bot } from "lucide-react";
import { cn } from "@/lib/cn";
import { useAgentStatus } from "./api";
import { isMockModel, modelDisplayName } from "./steps";

/**
 * The one place the UI names the model, so viewers always know whether replies come
 * from Muse Spark or the mock. Sending/payment modes live in the tooltip.
 */
export function AgentStatusCard() {
  const status = useAgentStatus();
  const data = status.data;
  if (status.isError) {
    return <p className="px-1 text-xs text-danger">Agent status unavailable</p>;
  }
  if (!data) return <div className="skeleton h-14 w-full rounded-xl" aria-hidden />;

  const mock = data.is_mock || isMockModel(data.model);
  const details = `Model id: ${data.model}\nInstagram: ${data.instagram_sending} · Payments: ${data.payments.replace(/_/g, " ")}`;
  return (
    <section
      aria-label="Sales agent status"
      title={details}
      className="space-y-1 rounded-xl border border-border bg-surface-strong/70 p-3 shadow-soft"
    >
      <p className="flex items-center gap-2 text-xs font-medium text-fg-muted">
        <Bot className="size-4 text-brand-fg" aria-hidden />
        Sales agent
        <span className="ml-auto inline-flex items-center gap-1.5 text-[11px] font-semibold">
          <span className="relative flex size-2">
            {data.enabled ? (
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-500 opacity-60 motion-reduce:hidden" />
            ) : null}
            <span
              className={cn(
                "relative inline-flex size-2 rounded-full",
                data.enabled ? "bg-emerald-500" : "bg-fg-subtle",
              )}
            />
          </span>
          {data.enabled ? "On" : "Off"}
        </span>
      </p>
      <p
        className={cn(
          "font-display text-sm font-semibold",
          mock ? "text-amber-800 dark:text-amber-200" : "text-fg",
        )}
      >
        {modelDisplayName(data.model)}
      </p>
      <p className="sr-only">
        Instagram sending: {data.instagram_sending}. Payments: {data.payments.replace(/_/g, " ")}.
      </p>
    </section>
  );
}
