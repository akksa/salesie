import { Trophy, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { PipelineCard, PipelineOut } from "@/api/types";
import { formatMoney } from "@/lib/format";

const TOAST_MS = 6000;

/**
 * Detects deals that newly appear in Won between polls (after the first load), so the
 * sale visibly lands: those cards flash and a toast announces the amount. Deals the
 * owner moved to Won themselves are excluded via `ownerMoved`.
 */
export function useWonArrivals(pipeline: PipelineOut | undefined, ownerMoved: ReadonlySet<number>) {
  const seen = useRef<ReadonlySet<number> | null>(null);
  const [celebrate, setCelebrate] = useState<ReadonlySet<number>>(new Set());
  const [toast, setToast] = useState<PipelineCard | null>(null);
  const won = pipeline?.columns.find((c) => c.stage === "won")?.deals;
  const signature = won?.map((d) => d.id).join(",");

  // biome-ignore lint/correctness/useExhaustiveDependencies: `signature` captures the won ids
  useEffect(() => {
    if (!won) return;
    const ids = new Set(won.map((d) => d.id));
    const previous = seen.current;
    seen.current = ids;
    if (previous === null) return;
    const arrived = won.filter((d) => !previous.has(d.id) && !ownerMoved.has(d.id));
    if (arrived.length === 0) return;
    setCelebrate(new Set(arrived.map((d) => d.id)));
    setToast(arrived[0] ?? null);
  }, [signature]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), TOAST_MS);
    return () => window.clearTimeout(timer);
  }, [toast]);

  return { celebrate, toast, dismissToast: () => setToast(null) };
}

export function WonToast({
  deal,
  currency,
  onDismiss,
}: {
  deal: PipelineCard | null;
  currency: string;
  onDismiss: () => void;
}) {
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed right-4 bottom-4 z-40 sm:right-6 sm:bottom-6"
    >
      {deal ? (
        <div
          role="status"
          className="pointer-events-auto flex items-center gap-3 rounded-2xl border border-emerald-400/50 bg-surface-strong py-3 pr-3 pl-4 shadow-lift animate-toast dark:border-emerald-400/30"
        >
          <span className="grid size-10 place-items-center rounded-full bg-emerald-500 text-white shadow-soft">
            <Trophy className="size-5" aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="font-display text-lg font-bold text-emerald-700 dark:text-emerald-300">
              {deal.amount_minor ? `+${formatMoney(deal.amount_minor, currency)} won` : "Deal won"}
            </p>
            <p className="truncate text-sm text-fg-muted">
              {deal.contact_name}
              {deal.product_name ? ` · ${deal.product_name}` : ""}
            </p>
          </div>
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss"
            className="grid size-8 cursor-pointer place-items-center rounded-lg text-fg-subtle transition-colors hover:bg-surface-muted hover:text-fg"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
      ) : null}
    </div>
  );
}
