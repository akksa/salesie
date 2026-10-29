import { Monitor, Moon, Sun } from "lucide-react";
import { useId } from "react";
import { cn } from "@/lib/cn";
import { type ThemePreference, useTheme } from "@/lib/theme";

const OPTIONS: { value: ThemePreference; label: string; Icon: typeof Sun }[] = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "system", label: "System", Icon: Monitor },
  { value: "dark", label: "Dark", Icon: Moon },
];

export function ThemeToggle() {
  const [preference, setPreference] = useTheme();
  // The toggle renders twice (desktop rail + mobile drawer); each needs its own radio group.
  const groupName = useId();
  return (
    <fieldset className="flex rounded-xl border border-border bg-surface-muted/70 p-1">
      <legend className="sr-only">Colour theme</legend>
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = preference === value;
        return (
          <label
            key={value}
            title={label}
            className={cn(
              "relative grid h-7 flex-1 cursor-pointer place-items-center rounded-lg text-fg-muted",
              "transition-[background-color,color,box-shadow] duration-200 hover:text-fg",
              "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-ring",
              active && "bg-surface-strong text-fg shadow-soft",
            )}
          >
            <input
              type="radio"
              name={groupName}
              value={value}
              checked={active}
              onChange={() => setPreference(value)}
              className="sr-only"
            />
            <Icon className="size-4" aria-hidden />
            <span className="sr-only">{label}</span>
          </label>
        );
      })}
    </fieldset>
  );
}
