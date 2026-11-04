import { CirclePause, Hand } from "lucide-react";
import { Link } from "react-router";
import type { ConversationListItem } from "@/api/types";
import { ChannelIcon } from "@/components/ChannelIcon";
import { Avatar } from "@/components/ui/Avatar";
import { cn } from "@/lib/cn";
import { formatAbsolute, formatRelative } from "@/lib/format";
import { previewText } from "./messageUtils";

/** The agent handed the chat over (refund, complaint, a question it couldn't answer). */
export function isHandoff(conversation: Pick<ConversationListItem, "paused_by">): boolean {
  return conversation.paused_by === "agent";
}

/** "Needs you" when the agent handed off; "Agent paused" when you paused it or took over. */
export function PausedBadge({ conversation }: { conversation: ConversationListItem }) {
  const handedOff = isHandoff(conversation);
  const Icon = handedOff ? Hand : CirclePause;
  const reason = conversation.paused_reason;
  return (
    <span
      title={reason ? `Agent paused: ${reason}` : "The AI agent is paused for this conversation"}
      className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-1.5 py-0.5 text-[11px] font-semibold text-amber-900 ring-1 ring-amber-300 ring-inset dark:bg-amber-400/15 dark:text-amber-200 dark:ring-amber-400/30"
    >
      <Icon className="size-3" aria-hidden />
      {handedOff ? "Needs you" : "Agent paused"}
    </span>
  );
}

/** One conversation row, used by the inbox list and the contact detail page. */
export function ConversationItem({
  conversation,
  active = false,
  isNew = false,
}: {
  conversation: ConversationListItem;
  active?: boolean;
  isNew?: boolean;
}) {
  const at = conversation.last_message?.sent_at ?? conversation.last_inbound_at;
  return (
    <Link
      to={`/inbox/${conversation.id}`}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group flex items-start gap-3 rounded-xl px-3 py-3 transition-[background-color,box-shadow] duration-200",
        active ? "bg-surface-strong shadow-soft ring-1 ring-brand-1/40" : "hover:bg-surface-muted/70",
        isNew && "animate-flash",
      )}
    >
      <span className="relative">
        <Avatar name={conversation.contact_name} />
        <ChannelIcon channel={conversation.channel} size="sm" className="absolute -right-1.5 -bottom-1.5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-2">
          <span className="truncate text-sm font-semibold text-fg">{conversation.contact_name}</span>
          <time
            dateTime={at ?? undefined}
            title={formatAbsolute(at)}
            className="shrink-0 text-[11px] text-fg-subtle"
          >
            {formatRelative(at)}
          </time>
        </span>
        <span className="mt-0.5 line-clamp-2 block text-xs break-words text-fg-muted">
          {previewText(conversation.last_message)}
        </span>
        {conversation.agent_paused ? (
          <span className="mt-1.5 block">
            <PausedBadge conversation={conversation} />
          </span>
        ) : null}
      </span>
    </Link>
  );
}
