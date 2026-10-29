import { ArrowRight } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link } from "react-router";
import type { SimulationResult as SimulationResultData } from "@/api/types";
import { useContacts } from "@/features/contacts/api";
import { cn } from "@/lib/cn";
import { AgentRunsPanel } from "./AgentRunsPanel";
import { useWebhookEvents } from "./api";
import { liveEvent } from "./simUtils";
import { WebhookStatusBadge } from "./WebhookStatusBadge";

export interface LastSimulation {
  kind: "comment" | "dm";
  username: string;
  event: SimulationResultData;
}

const LINK =
  "group inline-flex items-center gap-1.5 rounded-lg bg-surface-strong px-3 py-1.5 text-sm font-medium shadow-soft ring-1 ring-border " +
  "transition-[transform,box-shadow,color] duration-200 hover:-translate-y-px hover:text-brand-fg hover:shadow-lift";

function ResultLink({ to, children }: { to: string; children: string }) {
  return (
    <Link to={to} className={LINK}>
      {children}
      <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
    </Link>
  );
}

/** Shows what the simulated event produced, linking straight to the ids the backend returned. */
export function SimulationResult({ result }: { result: LastSimulation }) {
  const events = useWebhookEvents();
  const contacts = useContacts();
  const event = liveEvent(events.data, result.event);
  const contactName = contacts.data?.find((c) => c.id === event.contact_id)?.display_name;
  const failed = event.status === "failed";
  const ref = useRef<HTMLDivElement>(null);

  // On narrow screens the card renders below the forms; bring it into view once per send.
  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    ref.current?.scrollIntoView({ block: "nearest", behavior: reduced ? "auto" : "smooth" });
  }, []);

  const nothingCreated = event.contact_id === null && event.conversation_id === null;

  return (
    <div
      ref={ref}
      role="status"
      className={cn(
        "rounded-2xl border p-4 animate-enter",
        failed ? "border-danger/40 bg-danger-bg" : "border-emerald-500/30 bg-emerald-500/5",
      )}
    >
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <WebhookStatusBadge status={event.status} />
        <span className="text-fg-muted">
          Event #{event.id} · {result.kind === "comment" ? "comment" : "DM"} from{" "}
          <strong>@{result.username}</strong>
        </span>
      </div>
      {failed ? (
        <p className="mt-2 font-mono text-xs whitespace-pre-wrap break-words text-danger">
          {event.error ?? "No error text"}
        </p>
      ) : null}
      {nothingCreated ? (
        failed ? null : (
          <p className="mt-2 text-sm text-fg-subtle">No contact or conversation was created.</p>
        )
      ) : (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {event.contact_id !== null ? (
            <ResultLink to={`/contacts/${event.contact_id}`}>
              {contactName ? `Contact: ${contactName}` : "Open contact"}
            </ResultLink>
          ) : null}
          {event.conversation_id !== null ? (
            <ResultLink to={`/inbox/${event.conversation_id}`}>Open conversation</ResultLink>
          ) : null}
        </div>
      )}
      <AgentRunsPanel runs={result.event.agent_runs} />
    </div>
  );
}
