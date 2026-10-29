import type { DealStage } from "@/api/types";
import { cn } from "@/lib/cn";

export const STAGE_LABEL: Record<DealStage, string> = {
  new: "New",
  engaged: "Engaged",
  qualified: "Qualified",
  payment_sent: "Payment sent",
  won: "Won",
  lost: "Lost",
};

/**
 * Each stage gets its own hue AND a distinct dot shape, so the stage is never
 * conveyed by colour alone. Text/background pairs meet WCAG AA in both themes.
 */
const STAGE_STYLE: Record<DealStage, { badge: string; dot: string }> = {
  new: {
    badge:
      "bg-slate-100 text-slate-800 ring-slate-300 dark:bg-slate-400/15 dark:text-slate-200 dark:ring-slate-400/30",
    dot: "rounded-full border-2 border-current bg-transparent",
  },
  engaged: {
    badge: "bg-sky-100 text-sky-900 ring-sky-300 dark:bg-sky-400/15 dark:text-sky-200 dark:ring-sky-400/30",
    dot: "rounded-full bg-current",
  },
  qualified: {
    badge:
      "bg-violet-100 text-violet-900 ring-violet-300 dark:bg-violet-400/15 dark:text-violet-200 dark:ring-violet-400/30",
    dot: "rotate-45 rounded-[1px] bg-current",
  },
  payment_sent: {
    badge:
      "bg-amber-100 text-amber-900 ring-amber-300 dark:bg-amber-400/15 dark:text-amber-200 dark:ring-amber-400/30",
    dot: "rounded-[1px] bg-current",
  },
  won: {
    badge:
      "bg-emerald-100 text-emerald-900 ring-emerald-300 dark:bg-emerald-400/15 dark:text-emerald-200 dark:ring-emerald-400/30",
    dot: "rounded-full bg-current ring-2 ring-current/30",
  },
  lost: {
    badge:
      "bg-rose-100 text-rose-900 ring-rose-300 dark:bg-rose-400/15 dark:text-rose-200 dark:ring-rose-400/30",
    dot: "bg-current [clip-path:polygon(50%_100%,0_0,100%_0)]",
  },
};

export function DealStageBadge({ stage, className }: { stage: DealStage; className?: string }) {
  const style = STAGE_STYLE[stage];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset",
        "transition-colors duration-200",
        style.badge,
        className,
      )}
    >
      <span aria-hidden className={cn("inline-block size-2 shrink-0", style.dot)} />
      {STAGE_LABEL[stage]}
    </span>
  );
}
