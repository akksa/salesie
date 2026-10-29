import { RotateCcw } from "lucide-react";
import { Link } from "react-router";
import { errorMessage } from "@/api/client";
import type { WebhookEventOut } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { useReplayWebhookEvent } from "./api";

/** Replay button for a failed event, with row-scoped pending/error/outcome feedback. */
export function ReplayAction({ event }: { event: WebhookEventOut }) {
  const replay = useReplayWebhookEvent();
  const outcome = replay.data;

  return (
    <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-2">
      <Button
        variant="secondary"
        size="sm"
        loading={replay.isPending}
        onClick={() => replay.mutate(event.id)}
        icon={<RotateCcw className="size-3.5" aria-hidden />}
      >
        Replay
      </Button>
      <span className="text-xs text-fg-muted" aria-live="polite">
        {replay.isError ? (
          <span className="font-medium text-danger">Replay failed: {errorMessage(replay.error)}</span>
        ) : outcome?.status === "failed" ? (
          <span className="font-medium text-danger">Still failing, see the error above.</span>
        ) : (
          <>
            Fixed the cause, e.g. account ids in{" "}
            <Link to="/settings" className="font-medium text-brand-fg underline-offset-2 hover:underline">
              Settings
            </Link>
            ? Replay re-runs this delivery.
          </>
        )}
      </span>
    </div>
  );
}
