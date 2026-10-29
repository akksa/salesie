import { useAgentStatus } from "@/features/agent/api";
import { MockBadge } from "@/features/agent/RunStatusBadge";

/** Honest label for who is answering: the real model name, flagged when it's the mock. */
export function AgentModelNote() {
  const status = useAgentStatus().data;
  if (!status) return null;
  return (
    <p className="flex flex-wrap items-center gap-2 text-xs text-fg-subtle">
      {status.enabled ? "Replies come from" : "The agent is off. Configured model:"}
      <span className="font-mono text-fg-muted">{status.model}</span>
      {status.is_mock ? <MockBadge /> : null}
      <span>· Instagram sending: {status.instagram_sending}</span>
    </p>
  );
}
