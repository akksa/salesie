import type { JsonValue } from "@/api/types";
import { cn } from "@/lib/cn";
import { attributeToText } from "@/lib/format";

/** What the agent learned about a deal (e.g. size, colour, city) as compact chips. */
export function DealDetailChips({
  details,
  max = 6,
  className,
}: {
  details: Record<string, JsonValue> | undefined;
  max?: number;
  className?: string;
}) {
  const entries = Object.entries(details ?? {});
  if (entries.length === 0) return null;
  const hidden = entries.length - max;
  return (
    <ul className={cn("flex flex-wrap gap-1", className)} aria-label="Details the agent noted">
      {entries.slice(0, max).map(([key, value]) => (
        <li
          key={key}
          className="max-w-full truncate rounded-md bg-violet-50 px-1.5 py-0.5 text-[11px] text-violet-900 ring-1 ring-violet-200 ring-inset dark:bg-violet-400/10 dark:text-violet-100 dark:ring-violet-400/25"
          title={`${key}: ${attributeToText(value)}`}
        >
          <span className="opacity-70">{key}</span>{" "}
          <span className="font-semibold">{attributeToText(value)}</span>
        </li>
      ))}
      {hidden > 0 ? <li className="px-1 text-[11px] text-fg-subtle">+{hidden}</li> : null}
    </ul>
  );
}
