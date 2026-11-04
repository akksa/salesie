import { CreditCard, ExternalLink } from "lucide-react";
import { cn } from "@/lib/cn";

/** A checkout link rendered as a button, so raw payment URLs never appear on screen. */
export function CheckoutButton({ href, className }: { href: string; className?: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        "inline-flex items-center gap-2 rounded-xl bg-surface-strong px-3 py-2 text-xs font-semibold text-fg shadow-soft ring-1 ring-border",
        "transition-[transform,box-shadow] duration-200 hover:-translate-y-px hover:shadow-lift",
        className,
      )}
    >
      <CreditCard className="size-4 text-brand-fg" aria-hidden />
      Open checkout
      <ExternalLink className="size-3 text-fg-subtle" aria-hidden />
    </a>
  );
}
