import { Webhook } from "lucide-react";
import { useMemo, useState } from "react";
import type { WebhookEventOut, WebhookStatus } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { SkeletonRows } from "@/components/ui/Skeleton";
import { cn } from "@/lib/cn";
import { formatAbsolute, formatRelative } from "@/lib/format";
import { useNewIds } from "@/lib/useNewIds";
import { useWebhookEvents } from "./api";
import { ReplayAction } from "./ReplayAction";
import { WebhookStatusBadge } from "./WebhookStatusBadge";

const MAX_SHOWN = 30;

function EventRow({ event, isNew }: { event: WebhookEventOut; isNew: boolean }) {
  const failed = event.status === "failed";
  return (
    <li
      className={cn(
        "relative px-5 py-3.5 transition-colors duration-200 hover:bg-surface-muted/50",
        failed &&
          "bg-danger-bg/60 before:absolute before:inset-y-0 before:left-0 before:w-1 before:bg-danger",
        isNew && "animate-flash",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <WebhookStatusBadge status={event.status} />
        <span className="font-mono text-xs font-medium">{event.object_type}</span>
        {event.simulated ? <Badge tone="brand">Simulated</Badge> : <Badge tone="neutral">Meta</Badge>}
        <span className="ml-auto text-xs text-fg-subtle tabular-nums">
          #{event.id} ·{" "}
          <time dateTime={event.received_at} title={formatAbsolute(event.received_at)}>
            {formatRelative(event.received_at)}
          </time>
        </span>
      </div>
      {failed && event.error ? (
        <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-surface-strong/80 p-2.5 font-mono text-xs whitespace-pre-wrap break-words text-danger ring-1 ring-danger/20">
          {event.error}
        </pre>
      ) : null}
      {failed ? <ReplayAction event={event} /> : null}
    </li>
  );
}

const FILTERS: { value: WebhookStatus | undefined; label: string }[] = [
  { value: undefined, label: "All" },
  { value: "failed", label: "Failed" },
];

export function WebhookEventList() {
  const [status, setStatus] = useState<WebhookStatus | undefined>(undefined);
  const events = useWebhookEvents(status);
  // Newest first regardless of server order; never sort the cached array in place.
  const list = useMemo(
    () => events.data && [...events.data].sort((a, b) => b.id - a.id).slice(0, MAX_SHOWN),
    [events.data],
  );
  const fresh = useNewIds(useMemo(() => events.data?.map((e) => e.id), [events.data]));

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
        <div>
          <h2 className="text-base font-semibold">Webhook events</h2>
          <p className="text-xs text-fg-subtle">Every delivery, real or simulated. Refreshes every 3s.</p>
        </div>
        <fieldset className="flex rounded-xl border border-border bg-surface-muted/70 p-1">
          <legend className="sr-only">Filter events</legend>
          {FILTERS.map((filter) => (
            <button
              key={filter.label}
              type="button"
              aria-pressed={status === filter.value}
              onClick={() => setStatus(filter.value)}
              className={cn(
                "h-7 cursor-pointer rounded-lg px-3 text-xs font-medium text-fg-muted transition-[background-color,color,box-shadow] duration-200 hover:text-fg",
                status === filter.value && "bg-surface-strong text-fg shadow-soft",
              )}
            >
              {filter.label}
            </button>
          ))}
        </fieldset>
      </div>
      {events.isError ? (
        <ErrorBanner error={events.error} onRetry={() => events.refetch()} className="m-4" />
      ) : null}
      {events.isPending ? <SkeletonRows rows={4} /> : null}
      {list && list.length === 0 ? (
        <EmptyState
          icon={<Webhook className="size-6" aria-hidden />}
          title={status ? "No failed events" : "No events yet"}
        >
          {status ? "Everything processed cleanly." : "Send a fake comment or DM and watch it arrive here."}
        </EmptyState>
      ) : null}
      {list && list.length > 0 ? (
        <ul className="divide-y divide-border" aria-live="polite">
          {list.map((event) => (
            <EventRow key={event.id} event={event} isNew={fresh.has(event.id)} />
          ))}
        </ul>
      ) : null}
    </Card>
  );
}
