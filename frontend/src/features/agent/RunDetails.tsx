import { ChevronDown, Wrench } from "lucide-react";
import type { AgentRunOut } from "@/api/types";
import { cn } from "@/lib/cn";
import { formatAbsolute } from "@/lib/format";
import { MockBadge, RunStatusBadge } from "./RunStatusBadge";
import { type AgentStep, durationMs, isMockModel, parseSteps } from "./steps";

function Json({ value, error = false }: { value: unknown; error?: boolean }) {
  return (
    <pre
      className={cn(
        "mt-1 max-h-48 overflow-auto rounded-lg bg-surface-muted p-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap break-words ring-1 ring-border",
        error ? "text-danger ring-danger/30" : "text-fg-muted",
      )}
    >
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function StepView({ step, index }: { step: AgentStep; index: number }) {
  if (step.type === "model") {
    const calls = step.toolCalls.map((c) => c.name).join(", ");
    return (
      <li className="text-xs">
        <p className="font-semibold text-fg-muted">
          {index + 1}. Model {calls ? `called ${calls}` : "answered"}
        </p>
        {step.text ? (
          <p className="mt-0.5 whitespace-pre-wrap break-words text-fg-subtle">“{step.text}”</p>
        ) : null}
      </li>
    );
  }
  if (step.type === "tool") {
    return (
      <li className="text-xs">
        <p
          className={cn(
            "flex items-center gap-1.5 font-semibold",
            step.isError ? "text-danger" : "text-fg-muted",
          )}
        >
          <Wrench className="size-3" aria-hidden />
          {index + 1}. {step.name}
          {step.isError ? " (tool error)" : null}
        </p>
        <p className="mt-1 text-[11px] text-fg-subtle">Arguments</p>
        <Json value={step.arguments} />
        <p className="mt-1 text-[11px] text-fg-subtle">Result</p>
        <Json value={step.result} error={step.isError} />
      </li>
    );
  }
  return (
    <li className="text-xs">
      <p className="font-semibold text-fg-muted">{index + 1}. Other step</p>
      <Json value={step.raw} />
    </li>
  );
}

/** The run behind an agent message: model, status and every tool call with its result. */
export function RunSummary({ run }: { run: AgentRunOut }) {
  const steps = parseSteps(run.steps);
  const ms = durationMs(run);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-fg-subtle">
        <RunStatusBadge status={run.status} />
        <span className="font-mono">{run.model}</span>
        {isMockModel(run.model) ? <MockBadge /> : null}
        <span>
          Run #{run.id} · {run.trigger === "comment" ? "comment" : "DM"} ·{" "}
          <time dateTime={run.started_at} title={formatAbsolute(run.started_at)}>
            {ms === null ? "" : `${(ms / 1000).toFixed(1)}s`}
          </time>
        </span>
      </div>
      {run.error ? <p className="font-mono text-xs break-words text-danger">{run.error}</p> : null}
      {steps.length > 0 ? (
        <ol className="space-y-3">
          {steps.map((step, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: steps are an immutable, ordered log
            <StepView key={index} step={step} index={index} />
          ))}
        </ol>
      ) : (
        <p className="text-xs text-fg-subtle">No steps recorded.</p>
      )}
    </div>
  );
}

/** "Why?" disclosure under an agent message. Native <details> keeps it keyboard accessible. */
export function WhyDisclosure({
  run,
  loading,
  align,
}: {
  run: AgentRunOut | undefined;
  loading: boolean;
  align: "left" | "right";
}) {
  return (
    <details className={cn("group/why mt-1 w-full max-w-md", align === "right" ? "self-end" : "self-start")}>
      <summary
        className={cn(
          "flex cursor-pointer list-none items-center gap-1 px-1 text-[11px] font-semibold text-fg-subtle",
          "transition-colors hover:text-brand-fg [&::-webkit-details-marker]:hidden",
          align === "right" && "justify-end",
        )}
      >
        Why?
        <ChevronDown
          className="size-3 transition-transform duration-200 group-open/why:rotate-180"
          aria-hidden
        />
      </summary>
      <div className="mt-1.5 rounded-xl border border-border bg-surface-strong p-3 shadow-soft animate-enter">
        {run ? (
          <RunSummary run={run} />
        ) : (
          <p className="text-xs text-fg-subtle">
            {loading
              ? "Loading the agent's run…"
              : "This run is no longer available (only the latest 50 are kept)."}
          </p>
        )}
      </div>
    </details>
  );
}
