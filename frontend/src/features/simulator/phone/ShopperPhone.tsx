import { ChevronLeft, Dices, Info } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { PostOut, SimulationResult } from "@/api/types";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { useContacts } from "@/features/contacts/api";
import { usePosts } from "@/features/posts/api";
import { useBusiness } from "@/features/settings/api";
import { cn } from "@/lib/cn";
import { randomUsername, validateUsername } from "../simUtils";
import { BehindTheScenes, PhoneBubbles, TypingIndicator } from "./PhoneBubbles";
import { type ComposeMode, PhoneComposer } from "./PhoneComposer";
import { buildPhoneItems, knownUsernames } from "./phoneThread";
import { type SendInput, useShopperSession } from "./useShopperSession";

function ShopperPicker({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const contacts = useContacts();
  const listId = useId();
  const inputId = useId();
  const error = value ? validateUsername(value) : undefined;
  return (
    <div className="w-full max-w-[360px]">
      <label htmlFor={inputId} className="mb-1.5 block text-sm font-medium">
        Shopper
      </label>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-sm text-fg-subtle">
            @
          </span>
          <input
            id={inputId}
            list={listId}
            value={value}
            onChange={(e) => onChange(e.target.value.replace(/^@/, ""))}
            autoComplete="off"
            spellCheck={false}
            maxLength={30}
            aria-invalid={error ? true : undefined}
            placeholder="pick or type a username"
            className={cn(
              "h-10 w-full rounded-xl border bg-surface-strong pr-3 pl-7 text-sm shadow-sm transition-[border-color,box-shadow] focus:border-ring focus:outline-none focus:ring-4 focus:ring-ring/15",
              error ? "border-danger/70" : "border-border hover:border-border-strong",
            )}
          />
          <datalist id={listId}>
            {knownUsernames(contacts.data).map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
        </div>
        <Button
          variant="secondary"
          onClick={() => onChange(randomUsername())}
          icon={<Dices className="size-4" aria-hidden />}
        >
          New shopper
        </Button>
      </div>
      {error ? <p className="mt-1 text-xs font-medium text-danger">{error}</p> : null}
    </div>
  );
}

function PhoneHeader({ shopName }: { shopName: string }) {
  return (
    <div className="flex items-center gap-2.5 border-b border-border bg-surface-strong px-3 pt-9 pb-2.5">
      <ChevronLeft className="size-5 text-fg-muted" aria-hidden />
      <Avatar name={shopName} className="size-8" />
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold">{shopName}</p>
        <p className="text-[11px] text-fg-subtle">Instagram · usually replies instantly</p>
      </div>
    </div>
  );
}

/** Phone-shaped chat from the shopper's side. The demo's centrepiece. */
export function ShopperPhone({ onSent }: { onSent: (result: SimulationResult, input: SendInput) => void }) {
  const [username, setUsername] = useState(() => randomUsername());
  const [mode, setMode] = useState<ComposeMode>("comment");
  const [postId, setPostId] = useState("");
  const business = useBusiness();
  const posts = usePosts();
  const session = useShopperSession(username, onSent);
  const postList = posts.data ?? [];
  const selectedPost: PostOut | undefined = postList.find((p) => String(p.id) === postId) ?? postList[0];
  const postsById = useMemo(() => new Map(postList.map((p) => [p.id, p])), [postList]);
  const items = buildPhoneItems(
    session.conversation.data?.messages,
    session.contact.data?.engagements,
    postsById,
    session.pending,
  );
  const scrollRef = useRef<HTMLDivElement>(null);
  const usernameError = validateUsername(username);

  // biome-ignore lint/correctness/useExhaustiveDependencies: scroll when the thread grows or typing starts
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [items.length, session.sending, session.lastRuns]);

  const changeUsername = (next: string) => {
    setUsername(next);
    session.reset();
  };
  const send = (text: string) =>
    session.send({
      kind: mode,
      username: username.trim(),
      text,
      post: mode === "comment" ? selectedPost : undefined,
    });

  return (
    <div className="flex flex-col items-center gap-4">
      <ShopperPicker value={username} onChange={changeUsername} />
      <div className="relative w-full max-w-[360px] rounded-[2.75rem] bg-neutral-900 p-2.5 shadow-lift ring-1 ring-black/40 dark:bg-neutral-800 dark:shadow-[0_0_60px_-12px_rgb(217_54_122/0.45)] dark:ring-white/10">
        <div
          aria-hidden
          className="absolute top-4 left-1/2 z-10 h-6 w-24 -translate-x-1/2 rounded-full bg-black"
        />
        <div className="flex h-[min(640px,calc(100dvh-14rem))] min-h-[480px] flex-col overflow-hidden rounded-[2.2rem] bg-surface-strong">
          <PhoneHeader shopName={business.data?.name ?? "Your shop"} />
          <div
            ref={scrollRef}
            className="scrollbar-none flex-1 space-y-2.5 overflow-y-auto px-3 py-4"
            aria-live="polite"
          >
            {items.length === 0 && !session.sending ? (
              <p className="mt-10 flex flex-col items-center gap-2 px-6 text-center text-xs text-fg-subtle">
                <Info className="size-5" aria-hidden />
                Start like a real shopper: comment on a post, or send the shop a DM.
              </p>
            ) : null}
            <PhoneBubbles items={items} />
            {session.sending ? <TypingIndicator /> : null}
            <BehindTheScenes runs={session.lastRuns} />
            {session.error ? <ErrorBanner error={session.error} className="text-xs" /> : null}
          </div>
          <PhoneComposer
            mode={mode}
            onModeChange={setMode}
            posts={postList}
            postId={selectedPost ? String(selectedPost.id) : ""}
            onPostChange={setPostId}
            disabled={session.sending || usernameError !== undefined}
            onSend={send}
          />
        </div>
      </div>
    </div>
  );
}
