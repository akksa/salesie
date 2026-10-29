import { CircleAlert } from "lucide-react";
import {
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
  useId,
} from "react";
import { cn } from "@/lib/cn";

const CONTROL =
  "w-full rounded-xl border bg-surface-strong px-3 text-sm text-fg shadow-sm placeholder:text-fg-subtle " +
  "transition-[border-color,box-shadow,background-color] duration-200 " +
  "hover:border-border-strong focus:border-ring focus:outline-none focus:ring-4 focus:ring-ring/15 " +
  "disabled:cursor-not-allowed disabled:opacity-60";

function controlClass(error: string | undefined, extra?: string): string {
  return cn(
    CONTROL,
    error ? "border-danger/70 focus:border-danger focus:ring-danger/15" : "border-border",
    extra,
  );
}

interface FieldShellProps {
  label: string;
  error?: string | undefined;
  hint?: ReactNode;
  required?: boolean | undefined;
  className?: string | undefined;
  children: (ids: { id: string; describedBy: string | undefined }) => ReactNode;
}

/** Label + control + hint/error, with aria wiring so errors are announced. */
export function FieldShell({ label, error, hint, required, className, children }: FieldShellProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-sm font-medium text-fg">
        {label}
        {required ? (
          <span className="ml-0.5 text-brand-fg" aria-hidden>
            *
          </span>
        ) : null}
      </label>
      {children({ id, describedBy })}
      {hint && !error ? (
        <p id={hintId} className="text-xs text-fg-subtle">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="flex items-start gap-1 text-xs font-medium text-danger animate-enter">
          <CircleAlert className="mt-px size-3.5 shrink-0" aria-hidden />
          {error}
        </p>
      ) : null}
    </div>
  );
}

type Common = { label: string; error?: string | undefined; hint?: ReactNode; wrapperClassName?: string };

export function InputField({
  label,
  error,
  hint,
  wrapperClassName,
  className,
  ...rest
}: Common & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <FieldShell label={label} error={error} hint={hint} required={rest.required} className={wrapperClassName}>
      {({ id, describedBy }) => (
        <input
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={controlClass(error, cn("h-10", className))}
          {...rest}
        />
      )}
    </FieldShell>
  );
}

export function TextareaField({
  label,
  error,
  hint,
  wrapperClassName,
  className,
  ...rest
}: Common & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <FieldShell label={label} error={error} hint={hint} required={rest.required} className={wrapperClassName}>
      {({ id, describedBy }) => (
        <textarea
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={controlClass(error, cn("min-h-20 resize-y py-2", className))}
          {...rest}
        />
      )}
    </FieldShell>
  );
}

export function SelectField({
  label,
  error,
  hint,
  wrapperClassName,
  className,
  children,
  ...rest
}: Common & SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <FieldShell label={label} error={error} hint={hint} required={rest.required} className={wrapperClassName}>
      {({ id, describedBy }) => (
        <select
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={controlClass(error, cn("h-10 cursor-pointer pr-8", className))}
          {...rest}
        >
          {children}
        </select>
      )}
    </FieldShell>
  );
}
