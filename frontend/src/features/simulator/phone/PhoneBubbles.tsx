import { CreditCard, ExternalLink, MessageCircle } from "lucide-react";
import type { AgentRunOut } from "@/api/types";
import { LinkifiedText } from "@/components/LinkifiedText";
import { Thumb } from "@/components/ui/Thumb";
import { runNote } from "@/features/agent/steps";
import { cn } from "@/lib/cn";
import { formatTime } from "@/lib/format";
import { paymentLinks } from "@/lib/linkify";
import type { PhoneItem } from "./phoneThread";

function PayButton({ href }: { href: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="mt-1.5 inline-flex items-center gap-2 rounded-xl bg-surface-strong px-3 py-2 text-xs font-semibold text-fg shadow-soft ring-1 ring-border transition-[transform,box-shadow] duration-200 hover:-translate-y-px hover:shadow-lift"
    >
      <CreditCard className="size-4 text-brand-fg" aria-hidden />
      Open checkout
      <ExternalLink className="size-3 text-fg-subtle" aria-hidden />
    </a>
  );
}

function MessageBubble({ item }: { item: Extract<PhoneItem, { kind: "message" }> }) {
  const mine = item.side === "shopper";
  return (
    <div className={cn("flex flex-col animate-enter", mine ? "items-end" : "items-start")}>
      <div
        className={cn(
          "max-w-[82%] rounded-[1.25rem] px-3 py-2 text-[13px] leading-snug",
          mine
            ? "rounded-br-md bg-linear-to-br from-violet-600 to-fuchsia-600 text-white"
            : "rounded-bl-md bg-surface-muted text-fg ring-1 ring-border",
          item.pending && "opacity-60",
        )}
      >
        {item.text ? (
          <p className="whitespace-pre-wrap break-words">
            <LinkifiedText text={item.text} linkClassName={mine ? undefined : "text-brand-fg font-medium"} />
          </p>
        ) : (
          <p className="italic opacity-75">Attachment</p>
        )}
      </div>
      {!mine ? paymentLinks(item.text).map((href) => <PayButton key={href} href={href} />) : null}
      <span className="mt-0.5 px-1 text-[10px] text-fg-subtle">
        {item.pending ? "Sending…" : formatTime(item.at)}
      </span>
    </div>
  );
}

function CommentCard({ item }: { item: Extract<PhoneItem, { kind: "comment" }> }) {
  return (
    <div className={cn("flex flex-col items-end animate-enter", item.pending && "opacity-60")}>
      <div className="w-[82%] overflow-hidden rounded-2xl bg-surface-strong text-[13px] shadow-soft ring-1 ring-border">
        <div className="flex items-center gap-2 border-b border-border px-2.5 py-1.5 text-[11px] text-fg-subtle">
          <MessageCircle className="size-3.5" aria-hidden />
          You commented on a post
        </div>
        <div className="flex gap-2.5 p-2.5">
          <Thumb
            src={item.post?.image_url}
            alt={item.post?.caption ?? "Post"}
            className="size-10 rounded-lg"
          />
          <div className="min-w-0">
            <p className="truncate text-[11px] text-fg-subtle">{item.post?.caption ?? "Post"}</p>
            <p className="mt-0.5 break-words whitespace-pre-wrap text-fg">{item.text}</p>
          </div>
        </div>
      </div>
      <span className="mt-0.5 px-1 text-[10px] text-fg-subtle">
        {item.pending ? "Posting…" : formatTime(item.at)}
      </span>
    </div>
  );
}

export function TypingIndicator() {
  return (
    <div className="flex items-center gap-2 animate-enter" role="status" aria-label="Salesie is typing">
      <div className="flex gap-1 rounded-[1.25rem] rounded-bl-md bg-surface-muted px-3 py-3 ring-1 ring-border">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="size-1.5 animate-bounce rounded-full bg-fg-subtle"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>
    </div>
  );
}

/** Demo-only explanation when the agent ran but sent nothing to the shopper. */
export function BehindTheScenes({ runs }: { runs: AgentRunOut[] | null }) {
  if (runs === null) return null;
  const replied = runs.some((run) => run.status === "replied" || run.status === "handed_off");
  if (replied) return null;
  const notes = runs.map((run) => runNote(run)).filter((note): note is string => note !== null);
  const text = notes[0] ?? "The agent didn't run (it's off, or this chat is paused).";
  return (
    <p className="mx-auto max-w-[90%] rounded-lg border border-dashed border-border-strong px-2.5 py-1.5 text-center text-[11px] text-fg-subtle animate-enter">
      Demo note, not visible to the shopper: {text}
    </p>
  );
}

export function PhoneBubbles({ items }: { items: PhoneItem[] }) {
  return (
    <ol className="flex flex-col gap-2.5" aria-label="Shopper's conversation">
      {items.map((item) => (
        <li key={item.key}>
          {item.kind === "message" ? <MessageBubble item={item} /> : <CommentCard item={item} />}
        </li>
      ))}
    </ol>
  );
}
