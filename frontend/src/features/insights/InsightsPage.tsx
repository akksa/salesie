import { useSearchParams } from "react-router";
import { Card, CardHeader } from "@/components/ui/Card";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton, SkeletonRows } from "@/components/ui/Skeleton";
import { cn } from "@/lib/cn";
import { PERIODS, type Period, useInsights } from "./api";
import { ChannelTable } from "./ChannelTable";
import { FunnelChart } from "./FunnelChart";
import { KpiTiles } from "./KpiTiles";
import { PostRevenueList } from "./PostRevenueList";

function parsePeriod(raw: string | null): Period {
  const value = Number(raw);
  return PERIODS.find((p) => p === value) ?? 30;
}

function PeriodSwitch({ value, onChange }: { value: Period; onChange: (period: Period) => void }) {
  return (
    <fieldset className="flex rounded-xl border border-border bg-surface-muted/70 p-1">
      <legend className="sr-only">Period</legend>
      {PERIODS.map((period) => (
        <label
          key={period}
          className={cn(
            "cursor-pointer rounded-lg px-3 py-1.5 text-sm font-medium text-fg-muted",
            "transition-[background-color,color,box-shadow] duration-200 hover:text-fg",
            "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-ring",
            value === period && "bg-surface-strong text-fg shadow-soft",
          )}
        >
          <input
            type="radio"
            name="insights-period"
            className="sr-only"
            checked={value === period}
            onChange={() => onChange(period)}
          />
          {period} days
        </label>
      ))}
    </fieldset>
  );
}

function InsightsSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading insights">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
          <Skeleton key={i} className="h-24 rounded-2xl" />
        ))}
      </div>
      <Card>
        <SkeletonRows rows={4} />
      </Card>
    </div>
  );
}

export function InsightsPage() {
  const [params, setParams] = useSearchParams();
  const days = parsePeriod(params.get("days"));
  const insights = useInsights(days);
  const data = insights.data;

  return (
    <>
      <PageHeader
        eyebrow="Insights"
        title="What's selling"
        description="Leads, conversion and the posts that turned into revenue."
        actions={
          <PeriodSwitch value={days} onChange={(p) => setParams({ days: String(p) }, { replace: true })} />
        }
      />
      {insights.isError ? (
        <ErrorBanner error={insights.error} onRetry={() => insights.refetch()} className="mb-4" />
      ) : null}
      {insights.isPending ? <InsightsSkeleton /> : null}
      {data ? (
        <div className={cn("space-y-6 transition-opacity", insights.isPlaceholderData && "opacity-60")}>
          <KpiTiles data={data} />
          <div className="grid items-start gap-6 xl:grid-cols-[3fr_2fr]">
            <Card>
              <CardHeader
                title="Funnel"
                description="Deals that got at least this far, and how many each step kept"
              />
              <FunnelChart steps={data.funnel} />
            </Card>
            <Card className="overflow-hidden">
              <CardHeader title="By channel" />
              <ChannelTable rows={data.by_channel} currency={data.currency} />
            </Card>
          </div>
          <Card className="overflow-hidden">
            <CardHeader
              title="Which posts made money"
              description={`Last ${data.days} days, ranked by revenue then leads`}
            />
            <PostRevenueList rows={data.by_post} currency={data.currency} />
          </Card>
        </div>
      ) : null}
    </>
  );
}
