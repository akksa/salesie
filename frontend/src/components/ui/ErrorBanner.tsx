import { RefreshCw, TriangleAlert } from "lucide-react";
import { errorMessage } from "@/api/client";
import { cn } from "@/lib/cn";

export function ErrorBanner({
  error,
  onRetry,
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-3 rounded-xl border border-danger/30 bg-danger-bg px-4 py-3 text-sm text-danger animate-enter",
        className,
      )}
    >
      <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
      <p className="min-w-0 flex-1 break-words">{errorMessage(error)}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex cursor-pointer items-center gap-1 rounded-md px-1.5 font-medium underline-offset-2 transition-colors hover:underline"
        >
          <RefreshCw className="size-3.5" aria-hidden /> Retry
        </button>
      ) : null}
    </div>
  );
}
