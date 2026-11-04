import { Funnel } from "lucide-react";
import type { FunnelStep } from "@/api/types";
import { STAGE_FILL, STAGE_LABEL } from "@/components/DealStageBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn } from "@/lib/cn";
import { barPercent, formatCount, formatPercent, keptFrom } from "./metrics";

/**
 * Horizontal funnel. Each bar *is* a stage, so it uses that stage's colour; values
 * are labelled directly and the text is the accessible equivalent (bars are decorative).
 */
export function FunnelChart({ steps }: { steps: FunnelStep[] }) {
  const top = steps[0]?.reached ?? 0;
  if (top === 0) {
    return (
      <EmptyState icon={<Funnel className="size-6" aria-hidden />} title="No deals in this period">
        The funnel fills in as shoppers move from new to won.
      </EmptyState>
    );
  }
  return (
    <ol className="space-y-3.5 p-5" aria-label="Sales funnel: deals that reached each stage">
      {steps.map((step, index) => {
        const kept = keptFrom(steps[index - 1]?.reached, step.reached);
        const width = barPercent(step.reached, top);
        return (
          <li key={step.stage} className="grid gap-1.5 sm:grid-cols-[7.5rem_1fr] sm:items-center sm:gap-4">
            <span className="text-sm font-medium">{STAGE_LABEL[step.stage]}</span>
            {/* Bar, then its value right at the bar's end (no legend). Bars are decorative. */}
            <div className="flex min-w-0 items-center gap-2.5">
              <div
                aria-hidden
                className={cn(
                  "h-7 shrink-0 rounded-lg transition-[width] duration-500 ease-out",
                  STAGE_FILL[step.stage],
                )}
                style={{ width: `calc((100% - 9rem) * ${Math.max(width, step.reached > 0 ? 2 : 0) / 100})` }}
              />
              <span className="shrink-0 text-sm whitespace-nowrap tabular-nums">
                <strong className="font-semibold">
                  {formatCount(step.reached)} {step.reached === 1 ? "deal" : "deals"}
                </strong>
                {kept !== null ? <span className="text-fg-subtle"> · {formatPercent(kept)} kept</span> : null}
              </span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
