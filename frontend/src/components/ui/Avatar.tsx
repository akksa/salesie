import { cn } from "@/lib/cn";
import { initials } from "@/lib/format";

const HUES = [
  "from-orange-400 to-rose-500",
  "from-violet-400 to-fuchsia-500",
  "from-sky-400 to-indigo-500",
  "from-emerald-400 to-teal-500",
  "from-amber-400 to-orange-500",
  "from-pink-400 to-rose-500",
];

function hueFor(seed: string): string {
  const sum = [...seed].reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
  return HUES[sum % HUES.length] ?? HUES[0] ?? "";
}

export function Avatar({ name, className }: { name: string; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "grid size-9 shrink-0 place-items-center rounded-full bg-linear-to-br text-xs font-semibold text-white shadow-sm",
        hueFor(name),
        className,
      )}
    >
      {initials(name)}
    </span>
  );
}
