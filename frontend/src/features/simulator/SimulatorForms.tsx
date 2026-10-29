import { Dices, Send } from "lucide-react";
import { type FormEvent, useState } from "react";
import { fieldErrorsOf } from "@/api/client";
import type { PostOut } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { InputField, SelectField, TextareaField } from "@/components/ui/Field";
import { useSimulateComment, useSimulateDm } from "./api";
import type { LastSimulation } from "./SimulationResult";
import { COMMENT_IDEAS, cleanUsername, DM_IDEAS, randomUsername, validateUsername } from "./simUtils";

function UsernameField({
  value,
  onChange,
  error,
}: {
  value: string;
  onChange: (value: string) => void;
  error: string | undefined;
}) {
  return (
    <div className="flex items-start gap-2">
      <InputField
        label="Instagram username"
        required
        wrapperClassName="flex-1"
        autoComplete="off"
        spellCheck={false}
        maxLength={31}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        error={error}
        placeholder="style.diaries42"
      />
      <Button
        variant="secondary"
        size="icon"
        className="mt-[26px]"
        onClick={() => onChange(randomUsername())}
        aria-label="Random username"
        title="Random username"
        icon={<Dices className="size-4" aria-hidden />}
      />
    </div>
  );
}

function IdeaChips({ ideas, onPick }: { ideas: string[]; onPick: (idea: string) => void }) {
  return (
    <div className="-mt-1 flex flex-wrap gap-1.5">
      {ideas.map((idea) => (
        <button
          key={idea}
          type="button"
          onClick={() => onPick(idea)}
          className="cursor-pointer rounded-full bg-surface-muted px-2.5 py-1 text-xs text-fg-muted ring-1 ring-border transition-[background-color,color,transform] duration-200 hover:-translate-y-px hover:bg-surface-strong hover:text-fg"
        >
          {idea}
        </button>
      ))}
    </div>
  );
}

function textError(text: string, max: number): string | undefined {
  if (!text.trim()) return "Write something";
  if (text.length > max) return `Keep it under ${max} characters`;
  return undefined;
}

type Errors = Record<string, string | undefined>;

export function CommentForm({
  posts,
  onSent,
}: {
  posts: PostOut[];
  onSent: (result: LastSimulation) => void;
}) {
  const [postId, setPostId] = useState("");
  const [username, setUsername] = useState("");
  const [text, setText] = useState("");
  const [clientErrors, setClientErrors] = useState<Errors>({});
  const simulate = useSimulateComment();
  const errors: Errors = { ...fieldErrorsOf(simulate.error), ...clientErrors };
  const selectedPost = postId || (posts[0] ? String(posts[0].id) : "");

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {
      post_id: selectedPost ? undefined : "Register a post first",
      username: validateUsername(username),
      text: textError(text, 2200),
    };
    setClientErrors(found);
    if (Object.values(found).some(Boolean)) return;
    const name = cleanUsername(username);
    simulate.mutate(
      { post_id: Number(selectedPost), username: name, text: text.trim() },
      { onSuccess: (webhookEvent) => onSent({ kind: "comment", username: name, event: webhookEvent }) },
    );
  };

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      {simulate.error ? <ErrorBanner error={simulate.error} /> : null}
      <SelectField
        label="Post"
        required
        value={selectedPost}
        onChange={(e) => setPostId(e.target.value)}
        error={errors.post_id}
        disabled={posts.length === 0}
      >
        {posts.length === 0 ? <option value="">No posts registered</option> : null}
        {posts.map((post) => (
          <option key={post.id} value={post.id}>
            {(post.caption || post.external_id).slice(0, 60)}
            {post.product_name ? ` → ${post.product_name}` : " (no product)"}
          </option>
        ))}
      </SelectField>
      <UsernameField value={username} onChange={setUsername} error={errors.username} />
      <TextareaField
        label="Comment"
        required
        maxLength={2200}
        rows={2}
        value={text}
        onChange={(e) => setText(e.target.value)}
        error={errors.text}
        placeholder="How much is this?"
      />
      <IdeaChips ideas={COMMENT_IDEAS} onPick={setText} />
      <Button
        type="submit"
        loading={simulate.isPending}
        icon={<Send className="size-4" aria-hidden />}
        className="self-start"
      >
        Send comment
      </Button>
    </form>
  );
}

export function DmForm({ onSent }: { onSent: (result: LastSimulation) => void }) {
  const [username, setUsername] = useState("");
  const [text, setText] = useState("");
  const [clientErrors, setClientErrors] = useState<Errors>({});
  const simulate = useSimulateDm();
  const errors: Errors = { ...fieldErrorsOf(simulate.error), ...clientErrors };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = { username: validateUsername(username), text: textError(text, 1000) };
    setClientErrors(found);
    if (Object.values(found).some(Boolean)) return;
    const name = cleanUsername(username);
    simulate.mutate(
      { username: name, text: text.trim() },
      {
        onSuccess: (webhookEvent) => {
          onSent({ kind: "dm", username: name, event: webhookEvent });
          setText("");
        },
      },
    );
  };

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      {simulate.error ? <ErrorBanner error={simulate.error} /> : null}
      <UsernameField value={username} onChange={setUsername} error={errors.username} />
      <TextareaField
        label="Message"
        required
        maxLength={1000}
        rows={2}
        value={text}
        onChange={(e) => setText(e.target.value)}
        error={errors.text}
        placeholder="Hi! Is this still available?"
      />
      <IdeaChips ideas={DM_IDEAS} onPick={setText} />
      <Button
        type="submit"
        loading={simulate.isPending}
        icon={<Send className="size-4" aria-hidden />}
        className="self-start"
      >
        Send DM
      </Button>
    </form>
  );
}
