import { CircleDollarSign, Hand, MessageCircle, Percent, Target, Timer, Trophy, Users } from "lucide-react";
import type { ReactNode } from "react";
import type { InsightsOut } from "@/api/types";
import { cn } from "@/lib/cn";
import { formatMoney } from "@/lib/format";
import { formatCount, formatDuration, formatPercent } from "./metrics";

function Tile({
  label,
  value,
  icon,
  hint,
  emphasis = false,
  valueClassName,
  className,
}: {
  label: string;
  value: string;
  icon: ReactNode;
  hint?: ReactNode;
  emphasis?: boolean;
  valueClassName?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-1.5 rounded-2xl border border-border bg-surface p-4 shadow-soft",
        "transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-lift",
        emphasis && "ring-1 ring-brand-1/30",
        className,
      )}
    >
      <dt className="flex items-center gap-1.5 text-xs font-medium text-fg-muted">
        <span className="text-brand-fg">{icon}</span>
        {label}
      </dt>
      <dd className={cn("font-display text-2xl font-bold tabular-nums sm:text-3xl", valueClassName)}>
        {value}
      </dd>
      {hint ? <dd className="text-xs text-fg-subtle">{hint}</dd> : null}
    </div>
  );
}

export function KpiTiles({ data }: { data: InsightsOut }) {
  const icon = (Icon: typeof Users) => <Icon className="size-3.5" aria-hidden />;
  return (
    <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Tile
        label="Revenue"
        value={formatMoney(data.revenue_minor, data.currency) ?? "—"}
        icon={icon(CircleDollarSign)}
        emphasis
        className="col-span-2 justify-center bg-linear-to-br from-surface-strong to-emerald-500/5"
        valueClassName="text-4xl text-emerald-800 sm:text-4xl dark:text-emerald-200"
        hint={`from ${formatCount(data.won)} won deal${data.won === 1 ? "" : "s"}`}
      />
      <Tile label="Leads" value={formatCount(data.leads)} icon={icon(Users)} />
      <Tile label="Deals" value={formatCount(data.deals)} icon={icon(Target)} />
      <Tile label="Won" value={formatCount(data.won)} icon={icon(Trophy)} />
      <Tile
        label="Conversion"
        value={formatPercent(data.conversion_rate)}
        icon={icon(Percent)}
        hint="won ÷ deals opened"
      />
      <Tile
        label="Agent reply time"
        value={formatDuration(data.median_agent_reply_seconds)}
        icon={icon(Timer)}
        hint={
          <span className="flex flex-wrap items-center gap-1">
            <MessageCircle className="size-3" aria-hidden />
            median of {formatCount(data.agent_replies)} replies
          </span>
        }
      />
      <Tile
        label="Hand-offs"
        value={formatCount(data.handoffs)}
        icon={icon(Hand)}
        hint="chats the agent passed to you"
      />
    </dl>
  );
}
