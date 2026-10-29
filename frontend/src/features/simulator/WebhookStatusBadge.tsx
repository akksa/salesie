import { CircleAlert, CircleCheck, LoaderCircle } from "lucide-react";
import type { WebhookStatus } from "@/api/types";
import { Badge } from "@/components/ui/Badge";

export function WebhookStatusBadge({ status }: { status: WebhookStatus }) {
  if (status === "processed") {
    return (
      <Badge tone="success">
        <CircleCheck className="size-3" aria-hidden /> Processed
      </Badge>
    );
  }
  if (status === "failed") {
    return (
      <Badge tone="danger">
        <CircleAlert className="size-3" aria-hidden /> Failed
      </Badge>
    );
  }
  return (
    <Badge tone="info">
      <LoaderCircle className="size-3 animate-spin" aria-hidden /> Received
    </Badge>
  );
}
