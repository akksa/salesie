import { MessagesSquare } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import type { PostOut } from "@/api/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { SkeletonRows } from "@/components/ui/Skeleton";
import { useAgentRuns } from "@/features/agent/api";
import { useContact } from "@/features/contacts/api";
import { usePosts } from "@/features/posts/api";
import { useConversation } from "./api";
import { ThreadHeader } from "./ThreadHeader";
import { ThreadTimeline } from "./ThreadTimeline";
import { buildTimeline } from "./timeline";

function useThread(conversationId: number) {
  const conversation = useConversation(conversationId);
  const runs = useAgentRuns(conversationId);
  const contact = useContact(conversation.data?.contact_id ?? 0);
  const posts = usePosts();
  const data = conversation.data;

  const items = useMemo(
    () =>
      data
        ? buildTimeline({
            conversationId: data.id,
            messages: data.messages,
            runs: runs.data,
            // Comments are Instagram engagements; they give the agent's private replies their context.
            engagements: data.channel === "instagram" ? contact.data?.engagements : undefined,
            pausedReason: data.paused_reason,
          })
        : [],
    [data, runs.data, contact.data],
  );
  const postsById = useMemo(
    () => new Map<number, PostOut>((posts.data ?? []).map((post) => [post.id, post])),
    [posts.data],
  );
  return { conversation, runs, items, postsById };
}

function Thread({ conversationId }: { conversationId: number }) {
  const { conversation, runs, items, postsById } = useThread(conversationId);
  const endRef = useRef<HTMLDivElement>(null);
  const count = items.length;
  const data = conversation.data;

  // biome-ignore lint/correctness/useExhaustiveDependencies: scroll only when the timeline grows
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [count]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <ThreadHeader conversation={data} />
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4 py-5" aria-live="polite">
        {conversation.isError ? (
          <ErrorBanner error={conversation.error} onRetry={() => conversation.refetch()} />
        ) : null}
        {runs.isError ? (
          <ErrorBanner error={runs.error} onRetry={() => runs.refetch()} className="mb-3" />
        ) : null}
        {conversation.isPending ? <SkeletonRows rows={4} /> : null}
        {data && count === 0 ? (
          <p className="m-auto text-sm text-fg-subtle">No messages in this conversation yet.</p>
        ) : null}
        {data && count > 0 ? (
          <ThreadTimeline
            items={items}
            contactName={data.contact_name}
            runsLoading={runs.isPending}
            postsById={postsById}
          />
        ) : null}
        <div ref={endRef} />
      </div>
    </div>
  );
}

export function MessageThread({ conversationId }: { conversationId: number | null }) {
  if (conversationId === null) {
    return (
      <EmptyState
        icon={<MessagesSquare className="size-6" aria-hidden />}
        title="Pick a conversation"
        className="m-auto"
      >
        DMs from Instagram land here, along with the AI agent's replies and why it said them.
      </EmptyState>
    );
  }
  return <Thread conversationId={conversationId} />;
}
