import { Images } from "lucide-react";
import type { PostPerformance } from "@/api/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { Thumb } from "@/components/ui/Thumb";
import { formatMoney } from "@/lib/format";
import { safeHttpUrl } from "@/lib/url";
import { barPercent, formatCount } from "./metrics";

function Caption({ row }: { row: PostPerformance }) {
  const text = row.post.caption || `Post ${row.post.external_id}`;
  const href = safeHttpUrl(row.post.permalink);
  return href ? (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="line-clamp-2 text-sm font-medium break-words underline-offset-2 transition-colors hover:text-brand-fg hover:underline"
    >
      {text}
    </a>
  ) : (
    <p className="line-clamp-2 text-sm font-medium break-words">{text}</p>
  );
}

/** "Which posts made money": server order (revenue, then leads), one accent hue for magnitude. */
export function PostRevenueList({ rows, currency }: { rows: PostPerformance[]; currency: string }) {
  if (rows.length === 0) {
    return (
      <EmptyState icon={<Images className="size-6" aria-hidden />} title="No post activity yet">
        Once shoppers engage with registered posts, you'll see which ones bring in sales.
      </EmptyState>
    );
  }
  const max = Math.max(...rows.map((r) => r.revenue_minor));
  return (
    <ol className="divide-y divide-border" aria-label="Posts ranked by revenue">
      {rows.map((row, index) => (
        <li key={row.post.id} className="flex gap-3 px-5 py-4">
          <span className="w-5 shrink-0 pt-0.5 text-right font-display text-sm font-bold text-fg-subtle tabular-nums">
            {index + 1}
          </span>
          <Thumb src={row.post.image_url} alt="" className="size-12" />
          <div className="min-w-0 flex-1 space-y-1.5">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <Caption row={row} />
                {row.product_name ? (
                  <p className="truncate text-xs text-fg-subtle">{row.product_name}</p>
                ) : null}
              </div>
              <span className="shrink-0 font-display text-base font-bold tabular-nums">
                {formatMoney(row.revenue_minor, currency)}
              </span>
            </div>
            <div aria-hidden className="h-2 overflow-hidden rounded-full bg-surface-muted">
              <div
                className="brand-gradient h-full rounded-full transition-[width] duration-500 ease-out"
                style={{ width: `${barPercent(row.revenue_minor, max)}%` }}
              />
            </div>
            <p className="text-xs text-fg-muted tabular-nums">
              {formatCount(row.leads)} leads · {formatCount(row.deals)} deals · {formatCount(row.won)} won
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
