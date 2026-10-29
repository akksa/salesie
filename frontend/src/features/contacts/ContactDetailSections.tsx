import { Heart, MessageCircle } from "lucide-react";
import type { ConversationListItem, DealOut, EngagementOut, PostOut } from "@/api/types";
import { ChannelIcon } from "@/components/ChannelIcon";
import { DealDetailChips } from "@/components/DealDetails";
import { DealStageBadge } from "@/components/DealStageBadge";
import { Thumb } from "@/components/ui/Thumb";
import { ConversationItem } from "@/features/inbox/ConversationItem";
import { cn } from "@/lib/cn";
import { formatAbsolute, formatMoney, formatRelative } from "@/lib/format";

function SectionEmpty({ children }: { children: string }) {
  return <p className="px-5 py-8 text-center text-sm text-fg-subtle">{children}</p>;
}

function PostRef({ post, postId }: { post: PostOut | undefined; postId: number | null }) {
  if (postId === null) return null;
  return (
    <div className="mt-2 flex items-center gap-2.5 rounded-xl bg-surface-muted/70 p-2 ring-1 ring-border">
      <Thumb src={post?.image_url} alt={post?.caption ?? "Post"} className="size-9 rounded-lg" />
      <div className="min-w-0 text-xs">
        <p className="truncate text-fg-muted">{post?.caption || `Post #${postId}`}</p>
        {post?.product_name ? <p className="truncate font-medium text-fg">{post.product_name}</p> : null}
      </div>
    </div>
  );
}

export function EngagementTimeline({
  engagements,
  postsById,
}: {
  engagements: EngagementOut[];
  postsById: ReadonlyMap<number, PostOut>;
}) {
  if (engagements.length === 0) return <SectionEmpty>No comments or reactions yet.</SectionEmpty>;
  const sorted = [...engagements].sort((a, b) => b.occurred_at.localeCompare(a.occurred_at));
  return (
    <ol className="relative space-y-5 px-5 py-5 before:absolute before:top-6 before:bottom-6 before:left-[2.05rem] before:w-px before:bg-border">
      {sorted.map((engagement) => {
        const Icon = engagement.kind === "reaction" ? Heart : MessageCircle;
        return (
          <li key={engagement.id} className="relative flex gap-3 animate-enter">
            <span className="relative z-10 grid size-8 shrink-0 place-items-center rounded-full bg-surface-strong text-brand-fg ring-1 ring-border">
              <Icon className="size-4" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <p className="flex flex-wrap items-center gap-x-2 text-xs text-fg-subtle">
                <span className="font-semibold text-fg-muted capitalize">{engagement.kind}</span>
                <ChannelIcon channel={engagement.channel} size="sm" />
                <time dateTime={engagement.occurred_at} title={formatAbsolute(engagement.occurred_at)}>
                  {formatRelative(engagement.occurred_at)}
                </time>
              </p>
              {engagement.text ? (
                <blockquote className="mt-1.5 rounded-xl rounded-tl-sm bg-surface-strong px-3 py-2 text-sm whitespace-pre-wrap break-words shadow-soft ring-1 ring-border">
                  {engagement.text}
                </blockquote>
              ) : null}
              <PostRef
                post={engagement.post_id === null ? undefined : postsById.get(engagement.post_id)}
                postId={engagement.post_id}
              />
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function DealList({
  deals,
  currency,
  postsById,
}: {
  deals: DealOut[];
  currency: string;
  postsById: ReadonlyMap<number, PostOut>;
}) {
  if (deals.length === 0) return <SectionEmpty>No deals yet.</SectionEmpty>;
  return (
    <ul className="divide-y divide-border">
      {deals.map((deal) => {
        const amount = formatMoney(deal.amount_minor, currency);
        return (
          <li
            key={deal.id}
            className="space-y-2 px-5 py-4 transition-colors duration-200 hover:bg-surface-muted/40"
          >
            <div className="flex items-center justify-between gap-3">
              <DealStageBadge stage={deal.stage} />
              {amount ? (
                <span className={cn("font-display font-bold", deal.stage === "won" && "text-success")}>
                  {deal.stage === "won" ? `Won ${amount}` : amount}
                </span>
              ) : null}
            </div>
            <p className="font-medium">
              {deal.product_name ?? <span className="text-fg-subtle">No product linked</span>}
            </p>
            <DealDetailChips details={deal.details} />
            <p className="flex items-center gap-2 text-xs text-fg-subtle">
              <ChannelIcon channel={deal.channel} size="sm" />
              Updated{" "}
              <time dateTime={deal.updated_at} title={formatAbsolute(deal.updated_at)}>
                {formatRelative(deal.updated_at)}
              </time>
            </p>
            <PostRef
              post={deal.source_post_id === null ? undefined : postsById.get(deal.source_post_id)}
              postId={deal.source_post_id}
            />
          </li>
        );
      })}
    </ul>
  );
}

export function ConversationLinks({ conversations }: { conversations: ConversationListItem[] }) {
  if (conversations.length === 0) return <SectionEmpty>No direct messages yet.</SectionEmpty>;
  return (
    <ul className="space-y-1 p-2">
      {conversations.map((conversation) => (
        <li key={conversation.id}>
          <ConversationItem conversation={conversation} />
        </li>
      ))}
    </ul>
  );
}
