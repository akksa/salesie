import { Inbox } from "lucide-react";
import { useMemo } from "react";
import { useParams } from "react-router";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { SkeletonRows } from "@/components/ui/Skeleton";
import { cn } from "@/lib/cn";
import { useNewIds } from "@/lib/useNewIds";
import { useConversations } from "./api";
import { ConversationItem } from "./ConversationItem";
import { MessageThread } from "./MessageThread";

function parseId(raw: string | undefined): number | null {
  if (!raw || !/^\d+$/.test(raw)) return null;
  return Number(raw);
}

function ConversationList({ activeId }: { activeId: number | null }) {
  const conversations = useConversations();
  const list = conversations.data;
  const fresh = useNewIds(useMemo(() => list?.map((c) => c.id), [list]));

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-baseline justify-between border-b border-border px-4 py-3">
        <h1 className="text-lg font-semibold">Inbox</h1>
        {list ? (
          <span className="text-xs text-fg-subtle tabular-nums">
            {list.length} conversation{list.length === 1 ? "" : "s"}
          </span>
        ) : null}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {conversations.isError ? (
          <ErrorBanner error={conversations.error} onRetry={() => conversations.refetch()} className="m-2" />
        ) : null}
        {conversations.isPending ? <SkeletonRows rows={5} className="p-2" /> : null}
        {list && list.length === 0 ? (
          <EmptyState icon={<Inbox className="size-6" aria-hidden />} title="Inbox zero">
            New DMs appear here automatically.
          </EmptyState>
        ) : null}
        {list && list.length > 0 ? (
          <ul className="flex flex-col gap-1" aria-label="Conversations">
            {list.map((conversation) => (
              <li key={conversation.id}>
                <ConversationItem
                  conversation={conversation}
                  active={conversation.id === activeId}
                  isNew={fresh.has(conversation.id)}
                />
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}

/** Two-pane inbox. Below `lg` only one pane shows at a time: the list, or the open thread. */
export function InboxPage() {
  const params = useParams();
  const activeId = parseId(params.conversationId);
  const threadOpen = activeId !== null;

  return (
    <Card className="grid h-[calc(100dvh-7rem)] min-h-[28rem] overflow-hidden lg:h-[calc(100dvh-5rem)] lg:grid-cols-[22rem_1fr]">
      <section
        aria-label="Conversations"
        className={cn("min-h-0 flex-col border-border lg:flex lg:border-r", threadOpen ? "hidden" : "flex")}
      >
        <ConversationList activeId={activeId} />
      </section>
      <section
        aria-label="Messages"
        className={cn("min-h-0 flex-col lg:flex", threadOpen ? "flex" : "hidden")}
      >
        <MessageThread key={activeId ?? "none"} conversationId={activeId} />
      </section>
    </Card>
  );
}
