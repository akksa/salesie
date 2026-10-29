import type { AgentRunOut, EngagementOut, MessageOut } from "@/api/types";
import { runNote } from "@/features/agent/steps";

/** Everything that can appear in a conversation thread, in time order. */
export type TimelineItem =
  | { kind: "message"; key: string; at: string; message: MessageOut; run: AgentRunOut | undefined }
  | { kind: "note"; key: string; at: string; run: AgentRunOut; text: string }
  | { kind: "comment"; key: string; at: string; engagement: EngagementOut };

interface TimelineInput {
  conversationId: number;
  messages: MessageOut[];
  runs: AgentRunOut[] | undefined;
  engagements: EngagementOut[] | undefined;
  pausedReason: string | null;
}

/** Runs belong here if tied to this conversation, or to no conversation yet (e.g. a blocked comment reply). */
function relevantRuns(runs: AgentRunOut[] | undefined, conversationId: number): AgentRunOut[] {
  return (runs ?? []).filter((run) => run.conversation_id === null || run.conversation_id === conversationId);
}

/** Sort key: time, then a rank so a hand-off note sits right after the holding message it produced. */
function compare(a: { at: string; rank: number }, b: { at: string; rank: number }): number {
  return new Date(a.at).getTime() - new Date(b.at).getTime() || a.rank - b.rank;
}

export function buildTimeline(input: TimelineInput): TimelineItem[] {
  const runs = relevantRuns(input.runs, input.conversationId);
  const runById = new Map(runs.map((run) => [run.id, run]));
  const replyTime = new Map(
    input.messages.flatMap((m) => (m.agent_run_id === null ? [] : [[m.agent_run_id, m.sent_at] as const])),
  );

  const messages = input.messages.map((message) => ({
    rank: 0,
    at: message.sent_at,
    item: {
      kind: "message" as const,
      key: `m${message.id}`,
      at: message.sent_at,
      message,
      run: message.agent_run_id === null ? undefined : runById.get(message.agent_run_id),
    },
  }));

  const notes = runs.flatMap((run) => {
    const text = runNote(run, input.pausedReason);
    if (!text) return [];
    const at = replyTime.get(run.id) ?? run.finished_at;
    return [{ rank: 1, at, item: { kind: "note" as const, key: `r${run.id}`, at, run, text } }];
  });

  const comments = (input.engagements ?? [])
    .filter((e) => e.kind === "comment" && e.channel === "instagram")
    .map((engagement) => ({
      rank: -1,
      at: engagement.occurred_at,
      item: { kind: "comment" as const, key: `e${engagement.id}`, at: engagement.occurred_at, engagement },
    }));

  return [...comments, ...messages, ...notes].sort(compare).map((entry) => entry.item);
}
