import { ArrowRight, Hand } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { ApiError } from "@/api/client";
import type { DealDetail, DealStage } from "@/api/types";
import { ChannelIcon } from "@/components/ChannelIcon";
import { DealDetailChips } from "@/components/DealDetails";
import { DealStageBadge } from "@/components/DealStageBadge";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { SkeletonRows } from "@/components/ui/Skeleton";
import { formatMoney } from "@/lib/format";
import { useDeal } from "./api";
import { CashSaleForm } from "./CashSaleForm";
import { MoveMenu } from "./DealCard";
import { PaymentLinks, Section, SourcePostCard, StageTimeline } from "./DealSections";

const LINK =
  "group inline-flex items-center gap-1.5 rounded-lg bg-surface-muted px-3 py-1.5 text-sm font-medium ring-1 ring-border " +
  "transition-[transform,box-shadow,color] duration-200 hover:-translate-y-px hover:text-brand-fg hover:shadow-soft";

export function DealTitle({ deal, currency }: { deal: DealDetail | undefined; currency: string }) {
  if (!deal) return <div className="skeleton h-7 w-40" aria-hidden />;
  const amount = formatMoney(deal.amount_minor, currency);
  return (
    <div className="space-y-1.5">
      <h2 className="flex items-center gap-2 text-xl font-semibold">
        <ChannelIcon channel={deal.channel} size="sm" />
        <span className="truncate">{deal.contact_name}</span>
      </h2>
      <p className="flex flex-wrap items-center gap-2 text-sm text-fg-muted">
        <DealStageBadge stage={deal.stage} />
        {deal.product_name ?? "No product yet"}
        {amount ? <span className="font-display font-bold text-fg">{amount}</span> : null}
      </p>
    </div>
  );
}

type OnMove = (stage: DealStage, amountMinor?: number) => void;

/** Won needs a value: ask for one when the deal has no amount or no product to price it from. */
function CashSale({
  deal,
  currency,
  asking,
  pending,
  onMove,
  onDone,
}: {
  deal: DealDetail;
  currency: string;
  asking: boolean;
  pending: boolean;
  onMove: OnMove;
  onDone: () => void;
}) {
  if (asking && deal.stage !== "won") {
    return (
      <CashSaleForm
        currency={currency}
        initialMinor={deal.amount_minor}
        marking
        pending={pending}
        onSubmit={(amount) => {
          onMove("won", amount);
          onDone();
        }}
        onSkip={() => {
          onMove("won");
          onDone();
        }}
        onCancel={onDone}
      />
    );
  }
  if (deal.stage === "won" && deal.amount_minor === null) {
    return (
      <CashSaleForm
        currency={currency}
        initialMinor={null}
        marking={false}
        pending={pending}
        onSubmit={(amount) => onMove("won", amount)}
      />
    );
  }
  return null;
}

function Body({
  deal,
  currency,
  pending,
  onMove,
}: {
  deal: DealDetail;
  currency: string;
  pending: boolean;
  onMove: OnMove;
}) {
  const [askingAmount, setAskingAmount] = useState(false);
  const needsAmount = deal.amount_minor === null || deal.product_id === null;
  const handleMove = (stage: DealStage) => {
    if (stage === "won" && needsAmount) return setAskingAmount(true);
    setAskingAmount(false);
    onMove(stage);
  };
  return (
    <div className="space-y-7">
      {deal.needs_owner ? (
        <p className="flex items-start gap-2 rounded-xl bg-amber-50 px-3 py-2.5 text-sm text-amber-950 ring-1 ring-amber-300/60 dark:bg-amber-400/10 dark:text-amber-100 dark:ring-amber-400/25">
          <Hand className="mt-0.5 size-4 shrink-0" aria-hidden />
          The agent handed this chat to you. Open the conversation to reply.
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        {deal.conversation_id !== null ? (
          <Link to={`/inbox/${deal.conversation_id}`} className={LINK}>
            Open conversation
            <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
          </Link>
        ) : null}
        <Link to={`/contacts/${deal.contact_id}`} className={LINK}>
          Contact
          <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
        </Link>
        <MoveMenu deal={deal} onMove={handleMove} className="ml-auto h-9 text-sm" />
      </div>
      <CashSale
        deal={deal}
        currency={currency}
        asking={askingAmount}
        pending={pending}
        onMove={onMove}
        onDone={() => setAskingAmount(false)}
      />
      <Section title="What the agent learned">
        {Object.keys(deal.details).length > 0 ? (
          <DealDetailChips details={deal.details} max={20} size="md" />
        ) : (
          <p className="text-sm text-fg-subtle">Nothing noted yet.</p>
        )}
      </Section>
      <Section title="Source post">
        <SourcePostCard post={deal.source_post} />
      </Section>
      <Section title="Payment links">
        <PaymentLinks links={deal.payment_links} />
      </Section>
      <Section title="History">
        <StageTimeline changes={deal.stage_changes} />
      </Section>
    </div>
  );
}

export function DealPanel({
  dealId,
  currency,
  moveError,
  moving,
  onMove,
}: {
  dealId: number;
  currency: string;
  moveError: unknown;
  moving: boolean;
  onMove: OnMove;
}) {
  const deal = useDeal(dealId);
  if (deal.error instanceof ApiError && deal.error.status === 404) {
    return <p className="text-sm text-fg-muted">This deal doesn't exist any more.</p>;
  }
  return (
    <div className="space-y-4">
      {moveError ? <ErrorBanner error={moveError} /> : null}
      {deal.isError ? <ErrorBanner error={deal.error} onRetry={() => deal.refetch()} /> : null}
      {deal.isPending ? <SkeletonRows rows={4} className="p-0" /> : null}
      {deal.data ? <Body deal={deal.data} currency={currency} pending={moving} onMove={onMove} /> : null}
    </div>
  );
}
