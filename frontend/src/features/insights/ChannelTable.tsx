import type { ChannelPerformance } from "@/api/types";
import { CHANNEL_LABEL, ChannelIcon } from "@/components/ChannelIcon";
import { cn } from "@/lib/cn";
import { formatMoney } from "@/lib/format";
import { formatCount } from "./metrics";

const TH = "px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-fg-subtle";

export function ChannelTable({ rows, currency }: { rows: ChannelPerformance[]; currency: string }) {
  if (rows.length === 0) {
    return (
      <p className="px-5 py-8 text-center text-sm text-fg-subtle">No channel activity in this period.</p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">Deals, wins and revenue by channel</caption>
        <thead className="border-b border-border bg-surface-muted/40">
          <tr>
            <th scope="col" className={cn(TH, "text-left")}>
              Channel
            </th>
            <th scope="col" className={cn(TH, "text-right")}>
              Deals
            </th>
            <th scope="col" className={cn(TH, "text-right")}>
              Won
            </th>
            <th scope="col" className={cn(TH, "text-right")}>
              Revenue
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row) => (
            <tr key={row.channel} className="transition-colors hover:bg-surface-muted/40">
              <th scope="row" className="px-4 py-3 text-left font-medium">
                <span className="inline-flex items-center gap-2">
                  <ChannelIcon channel={row.channel} size="sm" />
                  {CHANNEL_LABEL[row.channel]}
                </span>
              </th>
              <td className="px-4 py-3 text-right tabular-nums">{formatCount(row.deals)}</td>
              <td className="px-4 py-3 text-right tabular-nums">{formatCount(row.won)}</td>
              <td className="px-4 py-3 text-right font-semibold tabular-nums">
                {formatMoney(row.revenue_minor, currency)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
