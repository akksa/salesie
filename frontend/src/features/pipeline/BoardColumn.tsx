import { type DragEvent, useState } from "react";
import type { DealStage, PipelineCard, PipelineColumn } from "@/api/types";
import { DealStageBadge, STAGE_FILL, STAGE_LABEL } from "@/components/DealStageBadge";
import { cn } from "@/lib/cn";
import { formatMoney } from "@/lib/format";
import { DealCard, DRAG_MIME } from "./DealCard";

export interface DragProps {
  currency: string;
  dragged: PipelineCard | null;
  celebrate: ReadonlySet<number>;
  onDragStart: (deal: PipelineCard) => void;
  onDragEnd: () => void;
  onMove: (dealId: number, stage: DealStage) => void;
}

/** HTML5 drop target for one stage. */
function useDropZone(stage: DealStage, dragged: PipelineCard | null, onMove: DragProps["onMove"]) {
  const [over, setOver] = useState(false);
  const accepts = dragged !== null && dragged.stage !== stage;
  const handlers = {
    onDragOver: (event: DragEvent) => {
      if (!accepts) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      if (!over) setOver(true);
    },
    onDragLeave: (event: DragEvent) => {
      if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOver(false);
    },
    onDrop: (event: DragEvent) => {
      event.preventDefault();
      setOver(false);
      const id = Number(event.dataTransfer.getData(DRAG_MIME));
      if (accepts && Number.isInteger(id) && id > 0) onMove(id, stage);
    },
  };
  return { over, accepts, handlers };
}

/** Zero-value columns show "—" rather than "$0.00". */
function Amount({ minor, currency, className }: { minor: number; currency: string; className?: string }) {
  return (
    <span className={cn("font-display font-bold tabular-nums", className)}>
      {minor > 0 ? formatMoney(minor, currency) : <span className="text-fg-subtle">—</span>}
    </span>
  );
}

function CardList({
  column,
  accepts,
  emptyLabel,
  props,
}: {
  column: PipelineColumn;
  accepts: boolean;
  emptyLabel: string;
  props: DragProps;
}) {
  return (
    <ul className="flex flex-col gap-2 p-2">
      {column.deals.map((deal) => (
        <li key={deal.id} className="animate-enter">
          <DealCard
            deal={deal}
            currency={props.currency}
            dragging={props.dragged?.id === deal.id}
            celebrate={props.celebrate.has(deal.id)}
            onDragStart={props.onDragStart}
            onDragEnd={props.onDragEnd}
            onMove={(stage) => props.onMove(deal.id, stage)}
          />
        </li>
      ))}
      {column.count > column.deals.length && column.deals.length > 0 ? (
        <li className="px-2 py-1.5 text-center text-xs font-medium text-fg-subtle">
          +{column.count - column.deals.length} more (showing the newest {column.deals.length})
        </li>
      ) : null}
      {column.deals.length === 0 ? (
        <li className="grid place-items-center rounded-xl border border-dashed border-border px-3 py-4 text-center text-xs text-fg-subtle xl:py-8">
          {accepts ? "Drop here" : emptyLabel}
        </li>
      ) : null}
    </ul>
  );
}

const COLUMN =
  "flex w-[17rem] shrink-0 snap-start flex-col rounded-2xl border bg-surface/70 backdrop-blur-sm xl:w-auto xl:min-w-0 xl:flex-1 " +
  "transition-[border-color,background-color,box-shadow] duration-200";

function dropClass(over: boolean, accepts: boolean): string {
  if (over) return "border-brand-1/70 bg-surface-strong shadow-lift ring-2 ring-brand-1/25";
  return accepts ? "border-dashed border-border-strong" : "border-border";
}

export function BoardColumn({ column, ...props }: { column: PipelineColumn } & DragProps) {
  const { over, accepts, handlers } = useDropZone(column.stage, props.dragged, props.onMove);
  return (
    <section
      aria-label={`${STAGE_LABEL[column.stage]}: ${column.count} deals`}
      {...handlers}
      className={cn(COLUMN, dropClass(over, accepts))}
    >
      <header className="rounded-t-2xl border-b border-border bg-surface-strong/90 px-3 py-2.5">
        <span aria-hidden className={cn("mb-2 block h-1 w-10 rounded-full", STAGE_FILL[column.stage])} />
        <p className="flex items-center gap-1.5 text-sm">
          <DealStageBadge stage={column.stage} />
          <span className="font-semibold text-fg-muted tabular-nums">· {column.count}</span>
        </p>
        <Amount minor={column.amount_minor} currency={props.currency} className="mt-1 block text-lg" />
      </header>
      <CardList column={column} accepts={accepts} emptyLabel="No deals" props={props} />
    </section>
  );
}

/**
 * Won and Lost share one "Closed" column so five columns fit at 1440px. Won cards
 * sit on top under an emerald header; Lost collapses into an "N lost" row. Each part
 * is its own drop target, and stages stay separate in data and in "Move to…".
 */
export function ClosedColumn({
  won,
  lost,
  ...props
}: { won: PipelineColumn; lost: PipelineColumn } & DragProps) {
  const wonZone = useDropZone("won", props.dragged, props.onMove);
  const lostZone = useDropZone("lost", props.dragged, props.onMove);
  return (
    <section
      aria-label={`Closed: ${won.count} won, ${lost.count} lost`}
      className={cn(COLUMN, "overflow-hidden", dropClass(false, wonZone.accepts || lostZone.accepts))}
    >
      <div {...wonZone.handlers} className={cn("transition-colors", wonZone.over && "bg-emerald-500/10")}>
        <header className="border-b border-emerald-300/60 bg-emerald-50 px-3 py-2.5 dark:border-emerald-400/20 dark:bg-emerald-400/10">
          <span aria-hidden className={cn("mb-2 block h-1 w-10 rounded-full", STAGE_FILL.won)} />
          <p className="flex items-center gap-1.5 text-sm">
            <DealStageBadge stage="won" />
            <span className="font-semibold text-fg-muted tabular-nums">· {won.count}</span>
          </p>
          <Amount
            minor={won.amount_minor}
            currency={props.currency}
            className="mt-1 block text-lg text-emerald-800 dark:text-emerald-200"
          />
        </header>
        <section aria-label={`Won: ${won.count} deals`}>
          <CardList column={won} accepts={wonZone.accepts} emptyLabel="No wins yet" props={props} />
        </section>
      </div>
      <details
        {...lostZone.handlers}
        className={cn("group/lost border-t border-border", lostZone.over && "bg-rose-500/10")}
      >
        <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2.5 text-sm transition-colors hover:bg-surface-muted/60 [&::-webkit-details-marker]:hidden">
          <DealStageBadge stage="lost" />
          <span className="font-semibold text-fg-muted tabular-nums">
            {lostZone.accepts ? "Drop to mark lost" : `${lost.count} lost`}
          </span>
          <span
            aria-hidden
            className="ml-auto text-xs text-fg-subtle transition-transform group-open/lost:rotate-180"
          >
            ▾
          </span>
        </summary>
        <section aria-label={`Lost: ${lost.count} deals`}>
          <CardList column={lost} accepts={lostZone.accepts} emptyLabel="Nothing lost" props={props} />
        </section>
      </details>
    </section>
  );
}
