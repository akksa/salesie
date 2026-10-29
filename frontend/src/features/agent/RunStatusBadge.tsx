import { Bot, CircleAlert, Hand, MessageCircleOff, ShieldBan } from "lucide-react";
import type { AgentRunStatus } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { RUN_STATUS_LABEL } from "./steps";

const TONE = {
  replied: "success",
  skipped: "neutral",
  handed_off: "warning",
  blocked: "info",
  failed: "danger",
} as const;

const ICON = {
  replied: Bot,
  skipped: MessageCircleOff,
  handed_off: Hand,
  blocked: ShieldBan,
  failed: CircleAlert,
};

export function RunStatusBadge({ status }: { status: AgentRunStatus }) {
  const Icon = ICON[status];
  return (
    <Badge tone={TONE[status]}>
      <Icon className="size-3" aria-hidden />
      {RUN_STATUS_LABEL[status]}
    </Badge>
  );
}

export function MockBadge({ className }: { className?: string }) {
  return (
    <Badge tone="warning" className={className} title="Replies come from a scripted mock, not Muse Spark">
      Mock model (no API credits)
    </Badge>
  );
}
