import { FlaskConical, MessageCircle, Send } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { PageHeader } from "@/components/ui/PageHeader";
import { SkeletonRows } from "@/components/ui/Skeleton";
import { usePosts } from "@/features/posts/api";
import { useAppConfig } from "@/features/settings/api";
import { AgentModelNote } from "./AgentModelNote";
import { ShopperPhone } from "./phone/ShopperPhone";
import { type LastSimulation, SimulationResult } from "./SimulationResult";
import { CommentForm, DmForm } from "./SimulatorForms";
import { WebhookEventList } from "./WebhookEventList";

function Disabled() {
  return (
    <Card>
      <EmptyState icon={<FlaskConical className="size-6" aria-hidden />} title="Simulator is off">
        Set SIMULATOR_ENABLED=true in the backend environment to fake Instagram comments and DMs.
      </EmptyState>
    </Card>
  );
}

function BehindTheScenesColumn({ last }: { last: LastSimulation | null }) {
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-brand-fg">Behind the scenes</p>
        <h2 className="mt-1 text-2xl font-bold">What Salesie did</h2>
        <p className="mt-1 text-sm text-fg-muted">
          Each message runs through the real webhook pipeline and the sales agent. Its reply, tool calls and
          the contact it created show up here.
        </p>
      </div>
      {last ? (
        <SimulationResult key={last.event.id} result={last} />
      ) : (
        <div className="rounded-2xl border border-dashed border-border-strong p-6 text-sm text-fg-subtle">
          Send something from the phone to see the agent's run.
        </div>
      )}
      <AgentModelNote />
    </div>
  );
}

function RawTools({ onSent }: { onSent: (last: LastSimulation) => void }) {
  const posts = usePosts();
  const postList = posts.data ?? [];
  return (
    <section aria-labelledby="raw-tools" className="mt-12">
      <h2 id="raw-tools" className="mb-1 text-xl font-bold">
        Raw webhook tools
      </h2>
      <p className="mb-5 text-sm text-fg-muted">Fire single events and inspect every delivery.</p>
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,26rem)_1fr]">
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader
              title="Fake an Instagram comment"
              description="Someone comments on one of your posts."
              action={<MessageCircle className="size-5 text-brand-fg" aria-hidden />}
            />
            <div className="p-5">
              {posts.isError ? (
                <ErrorBanner error={posts.error} onRetry={() => posts.refetch()} className="mb-4" />
              ) : null}
              {posts.isSuccess && postList.length === 0 ? (
                <p className="mb-4 rounded-xl bg-surface-muted px-3 py-2 text-sm text-fg-muted">
                  Comments need a post.{" "}
                  <Link to="/posts" className="font-medium text-brand-fg underline-offset-2 hover:underline">
                    Register one first
                  </Link>
                  .
                </p>
              ) : null}
              <CommentForm posts={postList} onSent={onSent} />
            </div>
          </Card>
          <Card>
            <CardHeader
              title="Fake a DM"
              description="Someone messages your Instagram account."
              action={<Send className="size-5 text-brand-fg" aria-hidden />}
            />
            <div className="p-5">
              <DmForm onSent={onSent} />
            </div>
          </Card>
        </div>
        <WebhookEventList />
      </div>
    </section>
  );
}

function SimulatorWorkbench() {
  const [last, setLast] = useState<LastSimulation | null>(null);
  return (
    <>
      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,380px)_1fr]">
        <ShopperPhone
          onSent={(event, input) => setLast({ kind: input.kind, username: input.username, event })}
        />
        <BehindTheScenesColumn last={last} />
      </div>
      <RawTools onSent={setLast} />
    </>
  );
}

export function SimulatorPage() {
  const appConfig = useAppConfig();
  return (
    <>
      <PageHeader
        eyebrow="Simulator"
        title="Be the shopper"
        description="Comment or DM like a real Instagram shopper and watch Salesie sell, live."
      />
      {appConfig.isError ? <ErrorBanner error={appConfig.error} onRetry={() => appConfig.refetch()} /> : null}
      {appConfig.isPending ? (
        <Card>
          <SkeletonRows rows={3} />
        </Card>
      ) : null}
      {appConfig.data ? appConfig.data.simulator_enabled ? <SimulatorWorkbench /> : <Disabled /> : null}
    </>
  );
}
