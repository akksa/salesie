import { Bot, CreditCard, ExternalLink, Settings2, User } from "lucide-react";
import type { Actor, PaymentLinkOut, PaymentStatus, PostBrief, StageChangeOut } from "@/api/types";
import { DealStageBadge } from "@/components/DealStageBadge";
import { Badge } from "@/components/ui/Badge";
import { Thumb } from "@/components/ui/Thumb";
import { cn } from "@/lib/cn";
import { formatAbsolute, formatMoney, formatRelative } from "@/lib/format";
import { safeHttpUrl } from "@/lib/url";

export const ACTOR_LABEL: Record<Actor, string> = { system: "System", agent: "Salesie agent", owner: "You" };
const ACTOR_ICON = { system: Settings2, agent: Bot, owner: User };
const PAYMENT_TONE = { open: "info", paid: "success", expired: "neutral" } as const;
const PAYMENT_LABEL: Record<PaymentStatus, string> = { open: "Open", paid: "Paid", expired: "Expired" };

export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-[0.12em] text-fg-subtle">{title}</h3>
      {children}
    </section>
  );
}

export function StageTimeline({ changes }: { changes: StageChangeOut[] }) {
  if (changes.length === 0) return <p className="text-sm text-fg-subtle">No stage changes recorded yet.</p>;
  return (
    <ol className="relative space-y-4 before:absolute before:top-2 before:bottom-2 before:left-[0.95rem] before:w-px before:bg-border">
      {changes.map((change, index) => {
        const Icon = ACTOR_ICON[change.actor];
        return (
          // biome-ignore lint/suspicious/noArrayIndexKey: stage changes have no id and are an append-only log
          <li key={index} className="relative flex gap-3">
            <span className="relative z-10 grid size-8 shrink-0 place-items-center rounded-full bg-surface-strong text-brand-fg ring-1 ring-border">
              <Icon className="size-4" aria-hidden />
            </span>
            <div className="min-w-0 flex-1 text-sm">
              <p className="flex flex-wrap items-center gap-1.5">
                <span className="font-semibold">{ACTOR_LABEL[change.actor]}</span>
                {change.from_stage ? (
                  <>
                    <span className="text-fg-subtle">moved it</span>
                    <DealStageBadge stage={change.from_stage} />
                    <span aria-hidden className="text-fg-subtle">
                      →
                    </span>
                    <span className="sr-only">to</span>
                  </>
                ) : (
                  <span className="text-fg-subtle">opened it as</span>
                )}
                <DealStageBadge stage={change.to_stage} />
              </p>
              {change.reason ? <p className="mt-1 break-words text-fg-muted">{change.reason}</p> : null}
              <time
                dateTime={change.created_at}
                title={formatAbsolute(change.created_at)}
                className="mt-0.5 block text-xs text-fg-subtle"
              >
                {formatRelative(change.created_at)}
              </time>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function PaymentLinks({ links }: { links: PaymentLinkOut[] }) {
  if (links.length === 0) return <p className="text-sm text-fg-subtle">No payment links sent yet.</p>;
  return (
    <ul className="space-y-2">
      {links.map((link) => {
        const href = safeHttpUrl(link.url);
        return (
          <li
            key={link.id}
            className={cn(
              "flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl p-3 ring-1",
              link.status === "paid"
                ? "bg-emerald-500/5 ring-emerald-500/30"
                : "bg-surface-muted/60 ring-border",
            )}
          >
            <CreditCard className="size-4 text-fg-subtle" aria-hidden />
            <span className="font-display font-bold">{formatMoney(link.amount_minor, link.currency)}</span>
            <span className="text-xs text-fg-muted">× {link.quantity}</span>
            <Badge tone={PAYMENT_TONE[link.status]}>{PAYMENT_LABEL[link.status]}</Badge>
            <span className="w-full text-xs text-fg-subtle sm:ml-auto sm:w-auto">
              {link.paid_at
                ? `Paid ${formatRelative(link.paid_at)}`
                : `Sent ${formatRelative(link.created_at)}`}
            </span>
            {href ? (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs font-medium text-brand-fg underline-offset-2 hover:underline"
              >
                {link.status === "paid" ? "View checkout" : "Open checkout"}{" "}
                <ExternalLink className="size-3 shrink-0" aria-hidden />
              </a>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

export function SourcePostCard({ post }: { post: PostBrief | null }) {
  if (!post) return <p className="text-sm text-fg-subtle">This lead didn't come from a registered post.</p>;
  const permalink = safeHttpUrl(post.permalink);
  const body = (
    <>
      <Thumb src={post.image_url} alt={post.caption ?? "Post"} className="size-16" />
      <div className="min-w-0 flex-1">
        <p className="line-clamp-3 text-sm break-words">{post.caption || "Instagram post (no caption)"}</p>
      </div>
      {permalink ? <ExternalLink className="size-4 shrink-0 text-fg-subtle" aria-hidden /> : null}
    </>
  );
  const className = "flex items-start gap-3 rounded-xl bg-surface-muted/60 p-3 ring-1 ring-border";
  return permalink ? (
    <a
      href={permalink}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        className,
        "transition-[box-shadow,transform] duration-200 hover:-translate-y-px hover:shadow-soft",
      )}
      aria-label={`Open the post on Instagram: ${post.caption ?? "no caption"}`}
    >
      {body}
    </a>
  ) : (
    <div className={className}>{body}</div>
  );
}
