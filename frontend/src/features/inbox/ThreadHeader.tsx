import { ArrowLeft, Hand, Pause, Play } from "lucide-react";
import { Link } from "react-router";
import { errorMessage } from "@/api/client";
import type { ConversationDetail } from "@/api/types";
import { CHANNEL_LABEL, ChannelIcon } from "@/components/ChannelIcon";
import { Button } from "@/components/ui/Button";
import { useSetAgentPaused } from "@/features/agent/api";
import { isHandoff } from "./ConversationItem";

function ToggleError({ error }: { error: unknown }) {
  return (
    <p role="alert" className="text-[11px] font-medium text-danger">
      {errorMessage(error)}
    </p>
  );
}

/** Header action while the agent is running. Resuming lives in the paused banner. */
function PauseButton({ conversationId }: { conversationId: number }) {
  const toggle = useSetAgentPaused(conversationId);
  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        variant="secondary"
        size="sm"
        loading={toggle.isPending}
        onClick={() => toggle.mutate(true)}
        icon={<Pause className="size-3.5" aria-hidden />}
        title="Stop the AI agent answering this chat"
      >
        Pause agent
      </Button>
      {toggle.isError ? <ToggleError error={toggle.error} /> : null}
    </div>
  );
}

/** Backend's reason after an owner message; the headline already says it, so don't repeat it. */
const TOOK_OVER_REASON = "you took over this chat";

function bannerText(conversation: ConversationDetail) {
  const reason = conversation.paused_reason;
  if (isHandoff(conversation)) {
    return (
      <>
        <strong className="font-semibold">The agent handed this chat to you</strong>
        {reason ? `: ${reason}` : "."}
      </>
    );
  }
  if (conversation.paused_by === "owner") {
    return (
      <>
        <strong className="font-semibold">You took over: the agent is paused</strong>
        {reason && reason !== TOOK_OVER_REASON ? <span className="opacity-75"> ({reason})</span> : null}
      </>
    );
  }
  return (
    <>
      <strong className="font-semibold">Agent paused</strong>
      {reason ? `: ${reason}` : null}. It won't reply here until you resume it.
    </>
  );
}

function PausedBanner({ conversation }: { conversation: ConversationDetail }) {
  const toggle = useSetAgentPaused(conversation.id);
  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-amber-300/60 bg-amber-50 px-4 py-2.5 text-sm text-amber-950 animate-enter dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-100"
    >
      <Hand className="size-4 shrink-0" aria-hidden />
      <p className="min-w-0 flex-1 break-words">{bannerText(conversation)}</p>
      <Button
        variant="secondary"
        size="sm"
        loading={toggle.isPending}
        onClick={() => toggle.mutate(false)}
        icon={<Play className="size-3.5" aria-hidden />}
        title="Let the AI agent answer this chat again"
      >
        Resume agent
      </Button>
      {toggle.isError ? <ToggleError error={toggle.error} /> : null}
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
            {conversation.agent_paused ? null : <PauseButton conversationId={conversation.id} />}
          </>
        ) : null}
      </header>
      {conversation?.agent_paused ? <PausedBanner conversation={conversation} /> : null}
    </>
  );
}
