import { ChevronRight } from "lucide-react";
import { Link } from "react-router";
import type { ContactListItem } from "@/api/types";
import { ChannelStack } from "@/components/ChannelIcon";
import { DealDetailChips } from "@/components/DealDetails";
import { DealStageBadge } from "@/components/DealStageBadge";
import { Avatar } from "@/components/ui/Avatar";
import { useCurrency } from "@/features/settings/api";
import { cn } from "@/lib/cn";
import { formatAbsolute, formatMoney, formatRelative } from "@/lib/format";
import { contactChannels, primaryUsername } from "./contactUtils";

const TH = "px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-fg-subtle";

function ContactRow({
  contact,
  isNew,
  currency,
}: {
  contact: ContactListItem;
  isNew: boolean;
  currency: string;
}) {
  const username = primaryUsername(contact.identities);
  const deal = contact.latest_deal;
  const wonAmount = deal ? formatMoney(deal.amount_minor, currency) : null;
  const showUsername = username !== null && username !== contact.display_name;
  return (
    <tr
      className={cn(
        "group relative transition-colors duration-200 hover:bg-surface-muted/60 focus-within:bg-surface-muted/60",
        isNew && "animate-flash",
      )}
    >
      <td className="px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <Avatar name={contact.display_name} />
          <div className="min-w-0">
            <Link
              to={`/contacts/${contact.id}`}
              className="block truncate font-medium text-fg after:absolute after:inset-0 focus-visible:outline-none"
            >
              {contact.display_name}
            </Link>
            <p className="truncate text-xs text-fg-muted">
              {showUsername ? `@${username}` : null}
              <span className="md:hidden">
                {showUsername && deal?.product_name ? " · " : null}
                {deal?.product_name}
              </span>
            </p>
          </div>
          {isNew ? <span className="sr-only">(new)</span> : null}
        </div>
      </td>
      <td className="hidden px-4 py-3 sm:table-cell">
        <ChannelStack channels={contactChannels(contact.identities)} />
      </td>
      <td className="px-4 py-3">
        {deal ? (
          <div className="flex flex-col items-start gap-1">
            <DealStageBadge stage={deal.stage} />
            {deal.stage === "won" && wonAmount ? (
              <span className="font-display text-xs font-bold text-success">{wonAmount}</span>
            ) : null}
          </div>
        ) : (
          <span className="text-xs text-fg-subtle">No deal</span>
        )}
      </td>
      <td className="hidden max-w-56 px-4 py-3 text-sm text-fg-muted md:table-cell">
        <p className="truncate">{deal?.product_name ?? <span className="text-fg-subtle">—</span>}</p>
        <DealDetailChips details={deal?.details} max={3} className="mt-1" />
      </td>
      <td className="hidden px-4 py-3 text-sm whitespace-nowrap text-fg-muted lg:table-cell">
        <time
          dateTime={contact.last_activity_at ?? undefined}
          title={formatAbsolute(contact.last_activity_at)}
        >
          {formatRelative(contact.last_activity_at)}
        </time>
      </td>
      <td className="w-8 pr-3 text-fg-subtle">
        <ChevronRight
          className="size-4 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-brand-fg"
          aria-hidden
        />
      </td>
    </tr>
  );
}

export function ContactsTable({
  contacts,
  fresh,
}: {
  contacts: ContactListItem[];
  fresh: ReadonlySet<number>;
}) {
  const currency = useCurrency();
  return (
    <div className="overflow-x-auto">
      <table className="w-full table-fixed border-collapse sm:table-auto">
        <thead className="border-b border-border bg-surface-muted/40">
          <tr>
            <th scope="col" className={TH}>
              Contact
            </th>
            <th scope="col" className={cn(TH, "hidden sm:table-cell")}>
              Channels
            </th>
            <th scope="col" className={cn(TH, "w-32 sm:w-auto")}>
              Stage
            </th>
            <th scope="col" className={cn(TH, "hidden md:table-cell")}>
              Product
            </th>
            <th scope="col" className={cn(TH, "hidden lg:table-cell")}>
              Last activity
            </th>
            <th scope="col" className="w-8">
              <span className="sr-only">Open</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {contacts.map((contact) => (
            <ContactRow
              key={contact.id}
              contact={contact}
              isNew={fresh.has(contact.id)}
              currency={currency}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
