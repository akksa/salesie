import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export function EmptyState({
  icon,
  title,
  children,
  action,
  className,
}: {
  icon: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center px-6 py-14 text-center animate-enter", className)}>
      <div className="mb-4 grid size-14 place-items-center rounded-2xl bg-surface-muted text-brand-fg ring-1 ring-border">
        {icon}
      </div>
      <h3 className="text-lg font-semibold">{title}</h3>
      {children ? <p className="mt-1 max-w-sm text-sm text-fg-muted">{children}</p> : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
