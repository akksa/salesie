import { DEAL_STAGES, type DealOut, type DealStage } from "@/api/types";
import { DealStageBadge } from "@/components/DealStageBadge";
import { useCurrency } from "@/features/settings/api";
import { cn } from "@/lib/cn";
import { formatMoney } from "@/lib/format";

/** Deal counts per stage. Acts as a filter for the contacts table (by latest deal stage). */
export function StageSummary({
  deals,
  selected,
  onSelect,
}: {
  deals: DealOut[] | undefined;
  selected: DealStage | null;
  onSelect: (stage: DealStage | null) => void;
}) {
  const currency = useCurrency();
  const wonTotal = deals
    ?.filter((deal) => deal.stage === "won")
    .reduce((sum, deal) => sum + (deal.amount_minor ?? 0), 0);
  const counts = DEAL_STAGES.map((stage) => ({
    stage,
    count: deals?.filter((deal) => deal.stage === stage).length ?? 0,
  }));

  return (
    <div className="-mx-4 mb-6 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <ul className="grid min-w-[36rem] grid-cols-6 gap-2" aria-label="Deals by stage">
        {counts.map(({ stage, count }) => {
          const active = selected === stage;
          return (
            <li key={stage}>
              <button
                type="button"
                aria-pressed={active}
                onClick={() => onSelect(active ? null : stage)}
                className={cn(
                  "flex h-full w-full cursor-pointer flex-col items-start gap-2 rounded-2xl border bg-surface p-3 text-left shadow-soft",
                  "transition-[transform,box-shadow,border-color,background-color] duration-200 hover:-translate-y-0.5 hover:shadow-lift",
                  active ? "border-brand-1/60 bg-surface-strong ring-2 ring-brand-1/20" : "border-border",
                )}
              >
                <DealStageBadge stage={stage} />
                <span className="font-display text-2xl font-bold tabular-nums">
                  {deals ? count : <span className="skeleton inline-block h-6 w-8 align-middle" />}
                </span>
                {stage === "won" && wonTotal ? (
                  <span className="-mt-1.5 text-xs font-semibold text-success">
                    {formatMoney(wonTotal, currency)}
                  </span>
                ) : null}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
