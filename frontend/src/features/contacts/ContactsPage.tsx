import { Search, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router";
import type { DealStage } from "@/api/types";
import { STAGE_LABEL } from "@/components/DealStageBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { PageHeader } from "@/components/ui/PageHeader";
import { SkeletonRows } from "@/components/ui/Skeleton";
import { useDeals } from "@/features/deals/api";
import { useAppConfig } from "@/features/settings/api";
import { useNewIds } from "@/lib/useNewIds";
import { useContacts } from "./api";
import { ContactsTable } from "./ContactsTable";
import { matchesSearch } from "./contactUtils";
import { StageSummary } from "./StageSummary";

export function ContactsPage() {
  const contacts = useContacts();
  const deals = useDeals();
  const simulatorEnabled = useAppConfig().data?.simulator_enabled ?? false;
  const [query, setQuery] = useState("");
  const [stage, setStage] = useState<DealStage | null>(null);

  const all = contacts.data;
  const fresh = useNewIds(useMemo(() => all?.map((c) => c.id), [all]));
  const visible = useMemo(
    () =>
      (all ?? []).filter(
        (c) => matchesSearch(c, query) && (stage === null || c.latest_deal?.stage === stage),
      ),
    [all, query, stage],
  );
  const filtering = query.trim() !== "" || stage !== null;

  return (
    <>
      <PageHeader
        eyebrow="Contacts"
        title="Your leads"
        description="Everyone who commented or messaged, linked to the post and product that caught their eye."
      />
      {deals.isError ? (
        <ErrorBanner error={deals.error} onRetry={() => deals.refetch()} className="mb-4" />
      ) : null}
      <StageSummary deals={deals.data} selected={stage} onSelect={setStage} />

      {contacts.isError ? (
        <ErrorBanner error={contacts.error} onRetry={() => contacts.refetch()} className="mb-4" />
      ) : null}

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b border-border px-4 py-3">
          <label className="relative min-w-0 flex-1 sm:max-w-xs">
            <span className="sr-only">Search contacts</span>
            <Search
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-subtle"
              aria-hidden
            />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search name or @username"
              className="h-9 w-full rounded-xl border border-border bg-surface-strong pr-3 pl-9 text-sm placeholder:text-fg-subtle transition-[border-color,box-shadow] duration-200 hover:border-border-strong focus:border-ring focus:outline-none focus:ring-4 focus:ring-ring/15"
            />
          </label>
          {stage ? (
            <Button variant="ghost" size="sm" onClick={() => setStage(null)}>
              Showing {STAGE_LABEL[stage]} · clear
            </Button>
          ) : null}
          <p className="ml-auto text-xs text-fg-subtle tabular-nums" aria-live="polite">
            {all ? `${visible.length} of ${all.length}` : null}
          </p>
        </div>

        {contacts.isPending ? <SkeletonRows rows={5} /> : null}
        {all && all.length === 0 ? (
          <EmptyState
            icon={<Users className="size-6" aria-hidden />}
            title="No leads yet"
            action={
              simulatorEnabled ? (
                <Link
                  to="/simulator"
                  className="brand-gradient inline-flex h-10 items-center rounded-xl px-4 text-sm font-medium text-white shadow-soft transition-[box-shadow,filter] duration-200 hover:shadow-lift hover:brightness-110"
                >
                  Simulate a comment
                </Link>
              ) : null
            }
          >
            When someone comments on a registered post or sends a DM, they show up here within seconds.
          </EmptyState>
        ) : null}
        {all && all.length > 0 && visible.length === 0 && filtering ? (
          <p className="px-4 py-10 text-center text-sm text-fg-muted">No contacts match these filters.</p>
        ) : null}
        {visible.length > 0 ? <ContactsTable contacts={visible} fresh={fresh} /> : null}
      </Card>
    </>
  );
}
