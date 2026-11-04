import type { AgentRunOut, AgentRunStatus } from "@/api/types";

/** Typed view of the server's untyped `steps` JSON. Unknown shapes are kept, not dropped. */
export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export type AgentStep =
  | { type: "model"; text: string | null; toolCalls: ToolCall[]; usage: Record<string, unknown> | null }
  | { type: "tool"; name: string; arguments: Record<string, unknown>; result: unknown; isError: boolean }
  | { type: "unknown"; raw: Record<string, unknown> };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function parseToolCall(value: unknown): ToolCall | null {
  if (!isRecord(value)) return null;
  const name = asString(value.name);
  if (!name) return null;
  return { id: asString(value.id) ?? "", name, arguments: isRecord(value.arguments) ? value.arguments : {} };
}

function parseStep(raw: Record<string, unknown>): AgentStep {
  if (raw.type === "model") {
    const calls = Array.isArray(raw.tool_calls) ? raw.tool_calls.map(parseToolCall) : [];
    return {
      type: "model",
      text: asString(raw.text),
      toolCalls: calls.filter((c): c is ToolCall => c !== null),
      usage: isRecord(raw.usage) ? raw.usage : null,
    };
  }
  if (raw.type === "tool" && typeof raw.name === "string") {
    return {
      type: "tool",
      name: raw.name,
      arguments: isRecord(raw.arguments) ? raw.arguments : {},
      result: raw.result,
      isError: isRecord(raw.result) && "error" in raw.result,
    };
  }
  return { type: "unknown", raw };
}

export function parseSteps(steps: unknown): AgentStep[] {
  return Array.isArray(steps) ? steps.filter(isRecord).map(parseStep) : [];
}

/** The reason passed to hand_off_to_owner, if the run handed off. */
export function handoffReason(run: AgentRunOut): string | null {
  for (const step of parseSteps(run.steps)) {
    if (step.type === "tool" && step.name === "hand_off_to_owner") {
      const reason = asString(step.arguments.reason);
      if (reason) return reason;
    }
  }
  return null;
}

export const RUN_STATUS_LABEL: Record<AgentRunStatus, string> = {
  replied: "Replied",
  skipped: "No reply",
  handed_off: "Handed to you",
  blocked: "Blocked",
  failed: "Error",
};

/** One-line, owner-facing explanation of a run that didn't simply reply. */
export function runNote(run: AgentRunOut, pausedReason?: string | null): string | null {
  switch (run.status) {
    case "replied":
      return null;
    case "handed_off":
      return `Handed to you · ${handoffReason(run) ?? pausedReason ?? "needs a person"}`;
    case "blocked":
      return `Couldn't reply: ${run.error ?? "Meta's messaging window doesn't allow it"}`;
    case "failed":
      return `Agent error: ${run.error ?? "unknown error"}`;
    case "skipped":
      return "Agent didn't reply: nothing to answer";
  }
}

/** Mirrors the backend's `is_mock` rule so per-run model names are labelled honestly too. */
export function isMockModel(model: string): boolean {
  return model.startsWith("mock");
}

export function durationMs(run: AgentRunOut): number | null {
  const ms = new Date(run.finished_at).getTime() - new Date(run.started_at).getTime();
  return Number.isFinite(ms) && ms >= 0 ? ms : null;
}

/**
 * Human name for a model id, shown once (sidebar). `muse-spark-1.3` / `muse-spark-1-3-…`
 * → "Muse Spark 1.3 · Meta Model API"; mock ids → "Mock model (no API credits)".
 */
export function modelDisplayName(model: string): string {
  if (isMockModel(model)) return "Mock model (no API credits)";
  const muse = /^muse-spark(?:-(\d+(?:[.-]\d+)*))?/i.exec(model);
  if (muse) {
    const version = muse[1]?.replace(/-/g, ".");
    return `Muse Spark${version ? ` ${version}` : ""} · Meta Model API`;
  }
  return model;
}
