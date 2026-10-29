import { ArrowLeft, UserX } from "lucide-react";
import { useMemo } from "react";
import { Link, useParams } from "react-router";
import { ApiError } from "@/api/client";
import type { ContactDetail, IdentityOut, PostOut } from "@/api/types";
import { CHANNEL_LABEL, ChannelIcon } from "@/components/ChannelIcon";
import { DealStageBadge } from "@/components/DealStageBadge";
import { Avatar } from "@/components/ui/Avatar";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Skeleton, SkeletonRows } from "@/components/ui/Skeleton";
import { usePosts } from "@/features/posts/api";
import { useCurrency } from "@/features/settings/api";
import { formatAbsolute, formatRelative } from "@/lib/format";
import { useContact } from "./api";
import { ConversationLinks, DealList, EngagementTimeline } from "./ContactDetailSections";

function BackLink() {
  return (
    <Link
      to="/contacts"
      className="mb-4 inline-flex items-center gap-1.5 rounded-lg text-sm font-medium text-fg-muted transition-[color,transform] duration-200 hover:-translate-x-0.5 hover:text-fg"
    >
      <ArrowLeft className="size-4" aria-hidden /> All contacts
    </Link>
  );
}

function IdentityChip({ identity }: { identity: IdentityOut }) {
  return (
    <li
      className="inline-flex items-center gap-2 rounded-full bg-surface-strong py-1 pr-3 pl-1 text-sm shadow-soft ring-1 ring-border"
      title={`${CHANNEL_LABEL[identity.channel]} id ${identity.external_id}`}
    >
      <ChannelIcon channel={identity.channel} size="sm" />
      <span className="font-medium">
        {identity.username ? `@${identity.username}` : identity.external_id}
      </span>
    </li>
  );
}

function ContactHeader({ contact }: { contact: ContactDetail }) {
  return (
    <header className="mb-6 flex flex-wrap items-start gap-4">
      <Avatar name={contact.display_name} className="size-16 text-lg" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-bold break-words sm:text-4xl">{contact.display_name}</h1>
          {contact.latest_deal ? <DealStageBadge stage={contact.latest_deal.stage} /> : null}
        </div>
        <ul className="mt-3 flex flex-wrap gap-2" aria-label="Identities">
          {contact.identities.map((identity) => (
            <IdentityChip key={`${identity.channel}:${identity.external_id}`} identity={identity} />
          ))}
        </ul>
        <p className="mt-3 text-xs text-fg-subtle">
          Last active{" "}
          <time
            dateTime={contact.last_activity_at ?? undefined}
            title={formatAbsolute(contact.last_activity_at)}
          >
            {formatRelative(contact.last_activity_at)}
          </time>
          {" · "}First seen {formatAbsolute(contact.created_at)}
        </p>
      </div>
    </header>
  );
}

function DetailSkeleton() {
  return (
    <div role="status" aria-label="Loading contact">
      <div className="mb-6 flex items-center gap-4">
        <Skeleton className="size-16 rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-8 w-1/3" />
          <Skeleton className="h-4 w-1/4" />
        </div>
      </div>
      <Card>
        <SkeletonRows rows={3} />
      </Card>
    </div>
  );
}

export function ContactDetailPage() {
  const { contactId } = useParams();
  const id = Number(contactId);
  const contact = useContact(id);
  const posts = usePosts();
  const currency = useCurrency();
  const postsById = useMemo(
    () => new Map<number, PostOut>((posts.data ?? []).map((post) => [post.id, post])),
    [posts.data],
  );

  const notFound =
    !Number.isInteger(id) || (contact.error instanceof ApiError && contact.error.status === 404);
  if (notFound) {
    return (
      <>
        <BackLink />
        <Card>
          <EmptyState icon={<UserX className="size-6" aria-hidden />} title="Contact not found">
            They may have been removed, or the link is out of date.
          </EmptyState>
        </Card>
      </>
    );
  }

  const data = contact.data;
  return (
    <>
      <BackLink />
      {contact.isError ? (
        <ErrorBanner error={contact.error} onRetry={() => contact.refetch()} className="mb-4" />
      ) : null}
      {contact.isPending ? <DetailSkeleton /> : null}
      {data ? (
        <>
          <ContactHeader contact={data} />
          <div className="grid gap-6 lg:grid-cols-[1fr_24rem]">
            <Card className="self-start">
              <CardHeader title="Engagements" description="Comments and reactions, newest first" />
              <EngagementTimeline engagements={data.engagements} postsById={postsById} />
            </Card>
            <div className="flex flex-col gap-6">
              <Card>
                <CardHeader title="Deals" />
                <DealList deals={data.deals} currency={currency} postsById={postsById} />
              </Card>
              <Card>
                <CardHeader title="Conversations" />
                <ConversationLinks conversations={data.conversations} />
              </Card>
            </div>
          </div>
        </>
      ) : null}
    </>
  );
}
