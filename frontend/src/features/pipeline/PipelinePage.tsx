import { Hand, SquareKanban, X } from "lucide-react";
import { useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { errorMessage } from "@/api/client";
import type { DealStage, PipelineCard } from "@/api/types";
import { STAGE_LABEL } from "@/components/DealStageBadge";
import { Card } from "@/components/ui/Card";
import { Drawer } from "@/components/ui/Drawer";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { useCurrency } from "@/features/settings/api";
import { formatMoney, toSentence } from "@/lib/format";
import { useDeal, useMoveDeal, usePipeline } from "./api";
import { BoardColumn, ClosedColumn } from "./BoardColumn";
import { DealPanel, DealTitle } from "./DealPanel";
import { findCard } from "./movePipeline";
import { useWonArrivals, WonToast } from "./wonArrivals";

interface MoveFailure {
  name: string;
  stage: DealStage;
  error: unknown;
}

function MoveFailureBanner({ failure, onDismiss }: { failure: MoveFailure; onDismiss: () => void }) {
  return (
    <div
      role="alert"
      className="mb-4 flex items-start gap-3 rounded-xl border border-danger/30 bg-danger-bg px-4 py-3 text-sm text-danger animate-enter"
    >
      <p className="min-w-0 flex-1 break-words">
        <strong className="font-semibold">
          Couldn't move {failure.name} to {STAGE_LABEL[failure.stage]}.
        </strong>{" "}
        {toSentence(errorMessage(failure.error))}
      </p>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="grid size-6 cursor-pointer place-items-center rounded-md transition-colors hover:bg-danger/10"
      >
        <X className="size-4" aria-hidden />
      </button>
    </div>
  );
}

function BoardSkeleton() {
  return (
    <div className="flex gap-3 overflow-hidden" role="status" aria-label="Loading pipeline">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="w-[17rem] shrink-0 space-y-2 rounded-2xl border border-border p-3">
          <Skeleton className="h-5 w-24" />
          <Skeleton className="h-20 w-full rounded-xl" />
          <Skeleton className="h-20 w-full rounded-xl" />
        </div>
      ))}
    </div>
  );
}

function parseId(raw: string | undefined): number | null {
  return raw && /^\d+$/.test(raw) ? Number(raw) : null;
}

export function PipelinePage() {
  const navigate = useNavigate();
  const dealId = parseId(useParams().dealId);
  const [dragged, setDragged] = useState<PipelineCard | null>(null);
  const [failure, setFailure] = useState<MoveFailure | null>(null);
  const pipeline = usePipeline({ paused: dragged !== null });
  const openDeal = useDeal(dealId);
  const move = useMoveDeal();
  const businessCurrency = useCurrency();
  const currency = pipeline.data?.currency ?? businessCurrency;
  const columns = pipeline.data?.columns ?? [];
  const openColumns = columns.filter((c) => c.stage !== "won" && c.stage !== "lost");
  const won = columns.find((c) => c.stage === "won");
  const lost = columns.find((c) => c.stage === "lost");
  const openValue = openColumns.reduce((sum, c) => sum + c.amount_minor, 0);
  const total = columns.reduce((sum, c) => sum + c.count, 0);
  const ownerMoved = useRef<Set<number>>(new Set());
  const wins = useWonArrivals(pipeline.data, ownerMoved.current);

  const moveDeal = (id: number, stage: DealStage, amountMinor?: number) => {
    const name = findCard(pipeline.data, id)?.contact_name ?? openDeal.data?.contact_name ?? "this deal";
    setFailure(null);
    const current = findCard(pipeline.data, id)?.stage ?? openDeal.data?.stage;
    // Recording an amount on a deal already in this stage is an amount-only PATCH.
    const sendStage = current === stage && amountMinor !== undefined ? undefined : stage;
    if (stage === "won") ownerMoved.current.add(id); // don't celebrate the owner's own move
    move.mutate(
      { dealId: id, stage: sendStage, amountMinor },
      { onError: (error) => setFailure({ name, stage, error }) },
    );
  };

  const dragProps = {
    currency,
    dragged,
    celebrate: wins.celebrate,
    onDragStart: setDragged,
    onDragEnd: () => setDragged(null),
    onMove: moveDeal,
  };

  return (
    <>
      <WonToast deal={wins.toast} currency={currency} onDismiss={wins.dismissToast} />
      <PageHeader
        eyebrow="Pipeline"
        title="Every deal, every stage"
        actions={
          pipeline.data && pipeline.data.needs_owner > 0 ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-3 py-1.5 text-sm font-semibold text-amber-950 ring-1 ring-amber-300 ring-inset dark:bg-amber-400/15 dark:text-amber-100 dark:ring-amber-400/30">
              <Hand className="size-4" aria-hidden />
              {pipeline.data.needs_owner} {pipeline.data.needs_owner === 1 ? "chat needs" : "chats need"} you
            </span>
          ) : null
        }
        description={
          pipeline.data ? (
            <>
              {total} deal{total === 1 ? "" : "s"} · {formatMoney(openValue, currency)} open ·{" "}
              <span className="font-semibold text-emerald-700 dark:text-emerald-300">
                {formatMoney(won?.amount_minor ?? 0, currency)} won
              </span>
              <span className="block text-xs text-fg-subtle lg:hidden">
                Tap “Move to…” on a card to change its stage.
              </span>
            </>
          ) : null
        }
      />
      {failure ? <MoveFailureBanner failure={failure} onDismiss={() => setFailure(null)} /> : null}
      {pipeline.isError ? (
        <ErrorBanner error={pipeline.error} onRetry={() => pipeline.refetch()} className="mb-4" />
      ) : null}
      {pipeline.isPending ? <BoardSkeleton /> : null}
      {pipeline.data && total === 0 ? (
        <Card>
          <EmptyState icon={<SquareKanban className="size-6" aria-hidden />} title="No deals yet">
            A deal opens when a shopper comments on a post or DMs you. Try the simulator to see one arrive.
          </EmptyState>
        </Card>
      ) : null}
      {pipeline.data && total > 0 ? (
        <div className="-mx-4 flex snap-x snap-mandatory scroll-px-4 items-start gap-3 overflow-x-auto px-4 pb-4 sm:-mx-6 sm:scroll-px-6 sm:px-6 lg:mx-0 lg:scroll-px-0 lg:px-0 xl:items-stretch">
          {openColumns.map((column) => (
            <BoardColumn key={column.stage} column={column} {...dragProps} />
          ))}
          {won && lost ? <ClosedColumn won={won} lost={lost} {...dragProps} /> : null}
        </div>
      ) : null}
      <Drawer
        open={dealId !== null}
        onClose={() => navigate("/")}
        title={<DealTitle deal={openDeal.data} currency={currency} />}
      >
        {dealId !== null ? (
          <DealPanel
            dealId={dealId}
            currency={currency}
            moving={move.isPending}
            moveError={failure && openDeal.data?.contact_name === failure.name ? failure.error : null}
            onMove={(stage, amountMinor) => moveDeal(dealId, stage, amountMinor)}
          />
        ) : null}
      </Drawer>
    </>
  );
}
