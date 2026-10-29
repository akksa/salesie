import { ChevronDown } from "lucide-react";
import type { AgentRunOut } from "@/api/types";
import { RunSummary } from "@/features/agent/RunDetails";
import { RunStatusBadge } from "@/features/agent/RunStatusBadge";
import { runNote } from "@/features/agent/steps";

/** What the agent did for the last simulated delivery: status, reply and every step. */
export function AgentRunsPanel({ runs }: { runs: AgentRunOut[] }) {
  if (runs.length === 0) {
    return (
      <p className="mt-3 text-sm text-fg-subtle">
        The agent didn't run: it's off, the chat is paused, or there was nothing new to answer.
      </p>
    );
  }
  return (
    <ul className="mt-3 space-y-2">
      {runs.map((run) => (
        <li key={run.id} className="rounded-xl bg-surface-strong/80 p-3 ring-1 ring-border">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <RunStatusBadge status={run.status} />
            <span className="text-xs text-fg-subtle">
              Agent run #{run.id} · {run.model}
            </span>
          </div>
          {run.reply_text ? (
            <p className="mt-2 line-clamp-3 text-sm break-words whitespace-pre-wrap">“{run.reply_text}”</p>
          ) : null}
          {runNote(run) ? <p className="mt-1 text-xs font-medium text-fg-muted">{runNote(run)}</p> : null}
          <details className="group/steps mt-2">
            <summary className="flex cursor-pointer list-none items-center gap-1 text-xs font-semibold text-fg-subtle transition-colors hover:text-brand-fg [&::-webkit-details-marker]:hidden">
              Show the agent's steps
              <ChevronDown className="size-3 transition-transform group-open/steps:rotate-180" aria-hidden />
            </summary>
            <div className="mt-2">
              <RunSummary run={run} />
            </div>
          </details>
        </li>
      ))}
    </ul>
  );
}
