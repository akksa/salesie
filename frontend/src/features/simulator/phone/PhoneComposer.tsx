import { ArrowUp, MessageCircle, Send } from "lucide-react";
import { type FormEvent, useId, useState } from "react";
import type { PostOut } from "@/api/types";
import { cn } from "@/lib/cn";

export type ComposeMode = "dm" | "comment";

const MAX = { dm: 1000, comment: 2200 } as const;

function ModeSwitch({ mode, onChange }: { mode: ComposeMode; onChange: (mode: ComposeMode) => void }) {
  const name = useId();
  const options: { value: ComposeMode; label: string; Icon: typeof Send }[] = [
    { value: "comment", label: "Comment on a post", Icon: MessageCircle },
    { value: "dm", label: "Send a DM", Icon: Send },
  ];
  return (
    <fieldset className="flex rounded-full bg-surface-muted p-0.5 text-[11px] ring-1 ring-border">
      <legend className="sr-only">What the shopper does</legend>
      {options.map(({ value, label, Icon }) => (
        <label
          key={value}
          className={cn(
            "flex flex-1 cursor-pointer items-center justify-center gap-1 rounded-full px-2 py-1 font-medium text-fg-muted",
            "transition-[background-color,color,box-shadow] duration-200 hover:text-fg",
            "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-ring",
            mode === value && "bg-surface-strong text-fg shadow-soft",
          )}
        >
          <input
            type="radio"
            name={name}
            className="sr-only"
            checked={mode === value}
            onChange={() => onChange(value)}
          />
          <Icon className="size-3" aria-hidden />
          {label}
        </label>
      ))}
    </fieldset>
  );
}

export function PhoneComposer({
  mode,
  onModeChange,
  posts,
  postId,
  onPostChange,
  disabled,
  onSend,
}: {
  mode: ComposeMode;
  onModeChange: (mode: ComposeMode) => void;
  posts: PostOut[];
  postId: string;
  onPostChange: (postId: string) => void;
  disabled: boolean;
  onSend: (text: string) => Promise<boolean>;
}) {
  const [text, setText] = useState("");
  const blocked = mode === "comment" && posts.length === 0;
  const canSend = !disabled && !blocked && text.trim().length > 0;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!canSend) return;
    if (await onSend(text.trim())) setText("");
  };

  return (
    <form onSubmit={submit} className="space-y-2 border-t border-border bg-surface-strong px-3 pt-2.5 pb-4">
      <ModeSwitch mode={mode} onChange={onModeChange} />
      {mode === "comment" ? (
        <select
          aria-label="Post to comment on"
          value={postId}
          onChange={(e) => onPostChange(e.target.value)}
          disabled={posts.length === 0}
          className="h-8 w-full cursor-pointer rounded-lg border border-border bg-surface-muted px-2 text-xs text-fg transition-colors focus:border-ring focus:outline-none"
        >
          {posts.length === 0 ? <option value="">No posts registered yet</option> : null}
          {posts.map((post) => (
            <option key={post.id} value={post.id}>
              {(post.caption || post.external_id).slice(0, 48)}
              {post.product_name ? ` · ${post.product_name}` : ""}
            </option>
          ))}
        </select>
      ) : null}
      <div className="flex items-end gap-2">
        <textarea
          aria-label={mode === "dm" ? "Message" : "Comment"}
          rows={1}
          maxLength={MAX[mode]}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) void submit(e);
          }}
          placeholder={mode === "dm" ? "Message…" : "Add a comment…"}
          className="max-h-24 min-h-9 flex-1 resize-none rounded-2xl border border-border bg-surface-muted px-3 py-2 text-[13px] text-fg placeholder:text-fg-subtle transition-[border-color,box-shadow] focus:border-ring focus:outline-none focus:ring-4 focus:ring-ring/15"
        />
        <button
          type="submit"
          disabled={!canSend}
          aria-label={mode === "dm" ? "Send message" : "Post comment"}
          className="grid size-9 shrink-0 cursor-pointer place-items-center rounded-full bg-linear-to-br from-violet-600 to-fuchsia-600 text-white shadow-soft transition-[transform,opacity] duration-200 hover:scale-105 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100"
        >
          <ArrowUp className="size-4" aria-hidden />
        </button>
      </div>
    </form>
  );
}
