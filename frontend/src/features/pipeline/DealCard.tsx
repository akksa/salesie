import { CirclePause, GripVertical, Hand } from "lucide-react";
import type { DragEvent } from "react";
import { Link } from "react-router";
import { DEAL_STAGES, type DealStage, type PipelineCard } from "@/api/types";
import { ChannelIcon } from "@/components/ChannelIcon";
import { STAGE_LABEL } from "@/components/DealStageBadge";
import { Thumb } from "@/components/ui/Thumb";
import { AUTHOR_PREFIX } from "@/features/inbox/messageUtils";
import { cn } from "@/lib/cn";
import { attributeToText, formatAbsolute, formatMoney, formatRelative } from "@/lib/format";
import { previewWithoutUrls } from "@/lib/linkify";

export const DRAG_MIME = "application/x-salesie-deal";

/** Keyboard/touch alternative to drag and drop. */
export function MoveMenu({
  deal,
  onMove,
  className,
}: {
  deal: { id: number; stage: DealStage; contact_name: string };
  onMove: (stage: DealStage) => void;
  className?: string;
}) {
  return (
    <select
      aria-label={`Move ${deal.contact_name}'s deal to…`}
      value=""
      onChange={(e) => {
        if (e.target.value) onMove(e.target.value as DealStage);
      }}
      className={cn(
        "h-7 cursor-pointer rounded-lg border border-border bg-surface-strong px-1.5 text-xs font-medium text-fg-muted",
        "transition-[border-color,color] duration-200 hover:border-border-strong hover:text-fg focus:border-ring focus:outline-none",
        className,
      )}
    >
      <option value="">Move to…</option>
      {DEAL_STAGES.filter((stage) => stage !== deal.stage).map((stage) => (
        <option key={stage} value={stage}>
          {STAGE_LABEL[stage]}
        </option>
      ))}
    </select>
  );
}

function OwnerHint({ deal }: { deal: PipelineCard }) {
  if (deal.needs_owner) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-1.5 py-0.5 text-[11px] font-semibold text-amber-900 ring-1 ring-amber-300 ring-inset dark:bg-amber-400/15 dark:text-amber-200 dark:ring-amber-400/30">
        <Hand className="size-3" aria-hidden /> Needs you
      </span>
    );
  }
  if (deal.agent_paused) {
    return (
      <span
        className="inline-flex items-center gap-1 text-[11px] font-medium text-fg-subtle"
        title="Agent paused"
      >
        <CirclePause className="size-3" aria-hidden /> Agent paused
      </span>
    );
  }
  return null;
}

/** Only when the post has an image: a caption alone would repeat the product line. */
function SourcePost({ deal }: { deal: PipelineCard }) {
  const post = deal.source_post;
  if (!post?.image_url) return null;
  return (
    <div className="flex items-center gap-2 rounded-lg bg-surface-muted/70 p-1.5">
      <Thumb src={post.image_url} alt="" className="size-8 rounded-md" />
      {post.caption ? <p className="line-clamp-1 min-w-0 text-xs text-fg-muted">{post.caption}</p> : null}
    </div>
  );
}

/** Top details the agent learned, e.g. "size L · colour sage". */
function TopDetails({ deal }: { deal: PipelineCard }) {
  const entries = Object.entries(deal.details).slice(0, 2);
  if (entries.length === 0) return null;
  return (
    <p className="truncate text-xs text-fg-muted">
      {entries.map(([key, value], index) => (
        <span key={key}>
          {index > 0 ? " · " : null}
          <span className="text-fg-subtle">{key}</span>{" "}
          <span className="font-semibold text-violet-800 dark:text-violet-200">{attributeToText(value)}</span>
        </span>
      ))}
    </p>
  );
}

function Preview({ deal }: { deal: PipelineCard }) {
  if (!deal.last_message) return null;
  const prefix = AUTHOR_PREFIX[deal.last_message_author ?? "contact"];
  return (
    <p className="line-clamp-2 text-[13px] leading-snug break-words text-fg-muted">
      {prefix ? <span className="font-semibold text-fg">{prefix} </span> : null}
      {previewWithoutUrls(deal.last_message)}
    </p>
  );
}

export function DealCard({
  deal,
  currency,
  dragging,
  celebrate = false,
  onDragStart,
  onDragEnd,
  onMove,
}: {
  deal: PipelineCard;
  currency: string;
  dragging: boolean;
  /** Just arrived in Won via polling: flash emerald once. */
  celebrate?: boolean;
  onDragStart: (deal: PipelineCard) => void;
  onDragEnd: () => void;
  onMove: (stage: DealStage) => void;
}) {
  const amount = formatMoney(deal.amount_minor, currency);
  const at = deal.last_activity_at ?? deal.updated_at;
  const handleDragStart = (event: DragEvent<HTMLElement>) => {
    event.dataTransfer.setData(DRAG_MIME, String(deal.id));
    event.dataTransfer.setData("text/plain", deal.contact_name);
    event.dataTransfer.effectAllowed = "move";
    onDragStart(deal);
  };

  return (
    <article
      draggable
      onDragStart={handleDragStart}
      onDragEnd={onDragEnd}
      className={cn(
        "group relative flex cursor-grab flex-col gap-2 rounded-xl border bg-surface-strong p-3 shadow-soft active:cursor-grabbing",
        "transition-[transform,box-shadow,border-color,opacity] duration-200 hover:-translate-y-0.5 hover:shadow-lift",
        deal.needs_owner
          ? "border-amber-400/70 dark:border-amber-400/40"
          : "border-border hover:border-brand-1/40",
        dragging && "rotate-1 opacity-50",
        celebrate && "animate-flash-won",
      )}
    >
      <GripVertical
        className="absolute top-2 right-1.5 size-4 text-fg-subtle opacity-0 transition-opacity group-hover:opacity-100"
        aria-hidden
      />
      <div className="flex min-w-0 items-center gap-2 pr-3">
        <ChannelIcon channel={deal.channel} size="sm" />
        <Link
          to={`/deals/${deal.id}`}
          draggable={false}
          className="min-w-0 truncate text-[15px] font-semibold text-fg after:absolute after:inset-0 after:rounded-xl focus-visible:outline-none"
        >
          {deal.contact_name}
        </Link>
      </div>
      <div className="-mt-1 flex items-baseline gap-2">
        <p className="min-w-0 flex-1 truncate text-[13px] text-fg-muted">
          {deal.product_name ?? "No product yet"}
        </p>
        {amount ? (
          <span className="shrink-0 font-display text-[15px] font-bold tabular-nums">{amount}</span>
        ) : null}
      </div>
      <TopDetails deal={deal} />
      <SourcePost deal={deal} />
      <Preview deal={deal} />
      <div className="flex flex-wrap items-center gap-2">
        <OwnerHint deal={deal} />
        <time dateTime={at} title={formatAbsolute(at)} className="text-xs text-fg-subtle">
          {formatRelative(at)}
        </time>
        <MoveMenu deal={deal} onMove={onMove} className="relative z-10 ml-auto" />
      </div>
    </article>
  );
}
