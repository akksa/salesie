import { ArrowLeft, Hand, Pause, Play } from "lucide-react";
import { Link } from "react-router";
import { errorMessage } from "@/api/client";
import type { ConversationDetail } from "@/api/types";
import { CHANNEL_LABEL, ChannelIcon } from "@/components/ChannelIcon";
import { Button } from "@/components/ui/Button";
import { useSetAgentPaused } from "@/features/agent/api";
import { OWNER_PAUSE_REASON } from "./ConversationItem";

function AgentToggle({ conversation }: { conversation: ConversationDetail }) {
  const toggle = useSetAgentPaused(conversation.id);
  const paused = conversation.agent_paused;
  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        variant={paused ? "primary" : "secondary"}
        size="sm"
        loading={toggle.isPending}
        onClick={() => toggle.mutate(!paused)}
        aria-pressed={paused}
        icon={paused ? <Play className="size-3.5" aria-hidden /> : <Pause className="size-3.5" aria-hidden />}
        title={paused ? "Let the AI agent answer this chat again" : "Stop the AI agent answering this chat"}
      >
        {paused ? "Resume agent" : "Pause agent"}
      </Button>
      {toggle.isError ? (
        <p role="alert" className="max-w-56 text-right text-[11px] font-medium text-danger">
          {errorMessage(toggle.error)}
        </p>
      ) : null}
    </div>
  );
}

function PausedBanner({ reason }: { reason: string | null }) {
  const handedOff = reason !== null && reason !== OWNER_PAUSE_REASON;
  return (
    <div
      role="status"
      className="flex items-start gap-2.5 border-b border-amber-300/60 bg-amber-50 px-4 py-2.5 text-sm text-amber-950 animate-enter dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-100"
    >
      <Hand className="mt-0.5 size-4 shrink-0" aria-hidden />
      <p className="min-w-0 break-words">
        {handedOff ? (
          <>
            <strong className="font-semibold">The agent handed this chat to you</strong>: {reason}
          </>
        ) : (
          <>
            <strong className="font-semibold">Agent paused</strong>
            {reason ? `: ${reason}` : null}. It won't reply here until you resume it.
          </>
        )}
      </p>
    </div>
  );
}

export function ThreadHeader({ conversation }: { conversation: ConversationDetail | undefined }) {
  return (
    <>
      <header className="flex items-center gap-3 border-b border-border px-4 py-3">
        <Link
          to="/inbox"
          aria-label="Back to conversations"
          className="grid size-9 place-items-center rounded-xl text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg lg:hidden"
        >
          <ArrowLeft className="size-5" aria-hidden />
        </Link>
        {conversation ? (
          <>
            <ChannelIcon channel={conversation.channel} />
            <div className="min-w-0 flex-1">
              <Link
                to={`/contacts/${conversation.contact_id}`}
                className="block truncate font-semibold transition-colors hover:text-brand-fg"
              >
                {conversation.contact_name}
              </Link>
              <p className="text-xs text-fg-subtle">{CHANNEL_LABEL[conversation.channel]} conversation</p>
            </div>
            <AgentToggle conversation={conversation} />
          </>
        ) : null}
      </header>
      {conversation?.agent_paused ? <PausedBanner reason={conversation.paused_reason} /> : null}
    </>
  );
}
