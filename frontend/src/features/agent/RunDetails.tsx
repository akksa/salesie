import { ChevronDown, Sparkles, Wrench } from "lucide-react";
import type { AgentRunOut } from "@/api/types";
import { cn } from "@/lib/cn";
import { formatAbsolute } from "@/lib/format";
import { previewWithoutUrls } from "@/lib/linkify";
import { RunStatusBadge } from "./RunStatusBadge";
import { type AgentStep, durationMs, parseSteps } from "./steps";

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
      <div className="text-xs">
        <p className="font-semibold text-fg-muted">
          {index + 1}. Model {calls ? `called ${calls}` : "answered"}
        </p>
        {step.text ? (
          <p className="mt-0.5 break-words text-fg-subtle">“{previewWithoutUrls(step.text)}”</p>
        ) : null}
      </div>
    );
  }
  if (step.type === "tool") {
    return (
      <div className="text-xs">
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
      </div>
    );
  }
  return (
    <div className="text-xs">
      <p className="font-semibold text-fg-muted">{index + 1}. Other step</p>
      <Json value={step.raw} />
    </div>
  );
}

/** The run behind an agent message: model, status and every tool call with its result. */
/**
 * `stagger`: reveal steps one by one (~60 ms apart), e.g. live in the simulator.
 * `header`: hide when the caller already shows status/model for this run.
 */
export function RunSummary({
  run,
  stagger = false,
  header = true,
}: {
  run: AgentRunOut;
  stagger?: boolean;
  header?: boolean;
}) {
  const steps = parseSteps(run.steps);
  const ms = durationMs(run);
  return (
    <div className="space-y-3">
      <div className={cn("flex flex-wrap items-center gap-2 text-xs text-fg-subtle", !header && "hidden")}>
        <RunStatusBadge status={run.status} />
        <span className="font-mono">{run.model}</span>
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
            <li
              // biome-ignore lint/suspicious/noArrayIndexKey: steps are an immutable, ordered log
              key={index}
              className={cn(stagger && "animate-enter")}
              style={stagger ? { animationDelay: `${index * 60}ms` } : undefined}
            >
              <StepView step={step} index={index} />
            </li>
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
  align: "left" | "right" | "center";
}) {
  return (
    <details
      className={cn(
        "group/why mt-1.5 flex w-full max-w-md flex-col",
        align === "right" && "items-end self-end",
        align === "left" && "items-start self-start",
        align === "center" && "items-center self-center",
      )}
    >
      <summary
        className={cn(
          "inline-flex w-fit cursor-pointer list-none items-center gap-1 rounded-full bg-surface-strong px-2 py-0.5",
          "text-xs font-semibold text-brand-fg ring-1 ring-brand-1/30 [&::-webkit-details-marker]:hidden",
          "transition-[background-color,box-shadow] hover:bg-surface-muted hover:ring-brand-1/60",
        )}
      >
        <Sparkles className="size-3.5" aria-hidden />
        Why?
        <ChevronDown
          className="size-3 transition-transform duration-200 group-open/why:rotate-180"
          aria-hidden
        />
      </summary>
      <div className="mt-1.5 w-full rounded-xl border border-border bg-surface-strong p-3 text-left shadow-soft animate-enter">
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
