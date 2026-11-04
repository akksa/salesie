import { CircleAlert, Hand, MessageCircle, MessageCircleOff, ShieldBan } from "lucide-react";
import type { AgentRunOut, MessageOut, PostOut } from "@/api/types";
import { CheckoutButton } from "@/components/CheckoutButton";
import { LinkifiedText } from "@/components/LinkifiedText";
import { WhyDisclosure } from "@/features/agent/RunDetails";
import { cn } from "@/lib/cn";
import { formatAbsolute, formatTime } from "@/lib/format";
import { splitPaymentLinks } from "@/lib/linkify";
import { authorLabel, sameDay } from "./messageUtils";
import type { TimelineItem } from "./timeline";

const BUBBLE: Record<MessageOut["author"], string> = {
  contact: "rounded-bl-md bg-surface-muted text-fg ring-1 ring-border",
  agent: "rounded-br-md brand-gradient text-white shadow-soft",
  owner: "rounded-br-md bg-fg text-bg shadow-soft",
};

const NOTE_ICON = {
  replied: MessageCircle,
  handed_off: Hand,
  blocked: ShieldBan,
  failed: CircleAlert,
  skipped: MessageCircleOff,
} as const;

const dayFormatter = new Intl.DateTimeFormat(undefined, { weekday: "short", month: "short", day: "numeric" });

function label(message: MessageOut, contactName: string): string {
  if (message.author === "agent" && message.agent_run_id === null) return "Salesie (automatic)";
  return authorLabel(message.author, contactName);
}

function Bubble({
  message,
  run,
  runsLoading,
  contactName,
  showAuthor,
}: {
  message: MessageOut;
  run: AgentRunOut | undefined;
  runsLoading: boolean;
  contactName: string;
  showAuthor: boolean;
}) {
  const outbound = message.direction === "outbound";
  const pending = message.id < 0; // optimistic owner message, see useSendOwnerMessage
  // Checkout links in Salesie's/your messages show as a button, not a raw URL.
  const { text, links } =
    outbound && message.text ? splitPaymentLinks(message.text) : { text: message.text, links: [] };
  return (
    <div className={cn("flex flex-col animate-enter", outbound ? "items-end" : "items-start")}>
      {showAuthor ? (
        <span className="mb-1 px-1 text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
          {label(message, contactName)}
        </span>
      ) : null}
      {text || links.length === 0 ? (
        <div
          className={cn(
            "max-w-[85%] rounded-2xl px-3.5 py-2 text-sm transition-opacity sm:max-w-[70%]",
            BUBBLE[message.author],
            pending && "opacity-60",
          )}
        >
          {text ? (
            <p className="whitespace-pre-wrap break-words">
              <LinkifiedText
                text={text}
                linkClassName={message.author === "contact" ? "text-brand-fg" : undefined}
              />
            </p>
          ) : (
            <p className="italic opacity-75">Attachment or unsupported message</p>
          )}
        </div>
      ) : null}
      {links.map((href) => (
        <CheckoutButton key={href} href={href} className="mt-1.5" />
      ))}
      <time
        dateTime={message.sent_at}
        title={formatAbsolute(message.sent_at)}
        className="mt-1 px-1 text-[10px] text-fg-subtle"
      >
        {pending ? "Sending…" : formatTime(message.sent_at)}
      </time>
      {message.agent_run_id !== null ? (
        <WhyDisclosure run={run} loading={runsLoading} align={outbound ? "right" : "left"} />
      ) : null}
    </div>
  );
}

function Note({ run, text }: { run: AgentRunOut; text: string }) {
  const Icon = NOTE_ICON[run.status];
  const tone =
    run.status === "failed"
      ? "text-danger bg-danger-bg ring-danger/25"
      : run.status === "handed_off"
        ? "text-amber-900 bg-amber-50 ring-amber-300/60 dark:text-amber-100 dark:bg-amber-400/10 dark:ring-amber-400/25"
        : "text-fg-muted bg-surface-muted ring-border";
  return (
    <div className="flex flex-col items-center animate-enter">
      <p
        className={cn(
          "inline-flex max-w-[90%] items-start gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium ring-1",
          tone,
        )}
      >
        <Icon className="mt-px size-3.5 shrink-0" aria-hidden />
        <span className="min-w-0 break-words">{text}</span>
      </p>
      {run.status !== "handed_off" ? <WhyDisclosure run={run} loading={false} align="center" /> : null}
    </div>
  );
}

function CommentNote({ text, post }: { text: string | null; post: PostOut | undefined }) {
  return (
    <div className="flex flex-col items-start animate-enter">
      <span className="mb-1 px-1 text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
        Commented on{" "}
        {post?.caption ? `“${post.caption.slice(0, 40)}${post.caption.length > 40 ? "…" : ""}”` : "a post"}
      </span>
      <p className="max-w-[85%] rounded-2xl rounded-bl-md border border-dashed border-border-strong px-3.5 py-2 text-sm break-words whitespace-pre-wrap text-fg sm:max-w-[70%]">
        {text ?? "(no text)"}
      </p>
    </div>
  );
}

export function ThreadTimeline({
  items,
  contactName,
  runsLoading,
  postsById,
}: {
  items: TimelineItem[];
  contactName: string;
  runsLoading: boolean;
  postsById: ReadonlyMap<number, PostOut>;
}) {
  return (
    <ol className="flex flex-col gap-3" aria-label="Conversation timeline">
      {items.map((item, index) => {
        const prev = items[index - 1];
        const newDay = !prev || !sameDay(prev.at, item.at);
        const prevAuthor = prev?.kind === "message" ? prev.message.author : null;
        return (
          <li key={item.key} className="flex flex-col gap-3">
            {newDay ? (
              <div className="my-2 flex items-center gap-3 text-[11px] font-medium text-fg-subtle">
                <span aria-hidden className="h-px flex-1 bg-border" />
                {dayFormatter.format(new Date(item.at))}
                <span aria-hidden className="h-px flex-1 bg-border" />
              </div>
            ) : null}
            {item.kind === "message" ? (
              <Bubble
                message={item.message}
                run={item.run}
                runsLoading={runsLoading}
                contactName={contactName}
                showAuthor={newDay || prevAuthor !== item.message.author}
              />
            ) : item.kind === "note" ? (
              <Note run={item.run} text={item.text} />
            ) : (
              <CommentNote
                text={item.engagement.text}
                post={item.engagement.post_id === null ? undefined : postsById.get(item.engagement.post_id)}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
