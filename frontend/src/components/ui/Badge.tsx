import type { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type Tone = "neutral" | "brand" | "success" | "warning" | "danger" | "info";

const TONES: Record<Tone, string> = {
  neutral: "bg-surface-muted text-fg-muted ring-border",
  brand:
    "bg-orange-100 text-orange-900 ring-orange-300/60 dark:bg-orange-500/15 dark:text-orange-200 dark:ring-orange-400/25",
  success:
    "bg-emerald-100 text-emerald-900 ring-emerald-300/60 dark:bg-emerald-500/15 dark:text-emerald-200 dark:ring-emerald-400/25",
  warning:
    "bg-amber-100 text-amber-900 ring-amber-300/60 dark:bg-amber-500/15 dark:text-amber-200 dark:ring-amber-400/25",
  danger:
    "bg-rose-100 text-rose-900 ring-rose-300/60 dark:bg-rose-500/15 dark:text-rose-200 dark:ring-rose-400/25",
  info: "bg-sky-100 text-sky-900 ring-sky-300/60 dark:bg-sky-500/15 dark:text-sky-200 dark:ring-sky-400/25",
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

export function Badge({ tone = "neutral", className, ...rest }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        "transition-colors duration-200",
        TONES[tone],
        className,
      )}
      {...rest}
    />
  );
}
