import { SendHorizontal, TriangleAlert } from "lucide-react";
import { type FormEvent, type KeyboardEvent, useId, useState } from "react";
import { ApiError, errorMessage } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";
import { toSentence } from "@/lib/format";
import { useSendOwnerMessage } from "./api";

/** The server limit is 1000 UTF-8 *bytes*: emoji and accented letters count as 2-4. */
const MAX_BYTES = 1000;
const encoder = new TextEncoder();

function utf8Bytes(text: string): number {
  return encoder.encode(text).length;
}
const IS_MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

const REPLY_RULES =
  "Instagram lets you message a shopper within 7 days of their last DM, or send one private reply to a comment from the last 7 days.";

/** The server's reason first (it says which rule applied), then the rules in plain words. */
function explain(error: unknown): { headline: string; detail: string | null } {
  if (error instanceof ApiError && error.status === 409) {
    return { headline: toSentence(error.message), detail: REPLY_RULES };
  }
  if (error instanceof ApiError && error.status === 502) {
    return {
      headline: "Instagram rejected the message, so nothing was sent.",
      detail: toSentence(error.message),
    };
  }
  return { headline: errorMessage(error), detail: null };
}

function SendError({ error, id }: { error: unknown; id: string }) {
  const { headline, detail } = explain(error);
  return (
    <div id={id} role="alert" className="flex items-start gap-2 text-xs text-danger animate-enter">
      <TriangleAlert className="mt-px size-3.5 shrink-0" aria-hidden />
      <p className="min-w-0 break-words">
        <span className="font-semibold">{headline}</span>
        {detail && detail !== headline ? <span className="block text-danger/80">{detail}</span> : null}
      </p>
    </div>
  );
}

/** Owner reply box. Ctrl/Cmd+Enter sends; sending pauses the agent on this chat. */
export function Composer({ conversationId, agentPaused }: { conversationId: number; agentPaused: boolean }) {
  const [text, setText] = useState("");
  const send = useSendOwnerMessage(conversationId);
  const errorId = useId();
  const trimmed = text.trim();
  const bytes = utf8Bytes(trimmed);
  const tooLong = bytes > MAX_BYTES;
  const canSend = trimmed.length > 0 && !tooLong && !send.isPending;

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (!canSend) return;
    send.mutate(trimmed, { onSuccess: () => setText("") });
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form onSubmit={submit} className="space-y-2 border-t border-border bg-surface-strong/80 px-4 py-3">
      {send.isError ? <SendError error={send.error} id={errorId} /> : null}
      <div className="flex items-end gap-2">
        <textarea
          aria-label="Reply as yourself"
          aria-describedby={send.isError ? errorId : undefined}
          rows={2}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            if (send.isError) send.reset();
          }}
          onKeyDown={onKeyDown}
          placeholder="Write a reply…"
          className="max-h-40 min-h-11 flex-1 resize-y rounded-xl border border-border bg-surface-strong px-3 py-2 text-sm text-fg placeholder:text-fg-subtle transition-[border-color,box-shadow] duration-200 hover:border-border-strong focus:border-ring focus:outline-none focus:ring-4 focus:ring-ring/15"
        />
        <Button
          type="submit"
          disabled={!canSend}
          loading={send.isPending}
          icon={<SendHorizontal className="size-4" aria-hidden />}
        >
          Send
        </Button>
      </div>
      <p className="flex flex-wrap justify-between gap-2 text-[11px] text-fg-subtle">
        <span>
          {agentPaused ? "The agent is paused here." : "Sending pauses the agent on this chat."}{" "}
          {IS_MAC ? "⌘" : "Ctrl"}+Enter to send
        </span>
        {/* Hidden until 80% of Instagram's byte limit (emoji/accents count as 2-4 bytes). */}
        {bytes >= MAX_BYTES * 0.8 ? (
          <span
            aria-live="polite"
            className={cn(
              "font-medium text-amber-700 dark:text-amber-300",
              tooLong && "font-semibold text-danger",
            )}
            title={`${bytes}/${MAX_BYTES} bytes; emoji and accented letters use more than one byte`}
          >
            {tooLong ? "Too long for Instagram: shorten it a little" : "Almost at Instagram's limit"}
          </span>
        ) : null}
      </p>
    </form>
  );
}
