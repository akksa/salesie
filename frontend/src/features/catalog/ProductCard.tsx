import { Pencil } from "lucide-react";
import type { ProductOut } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Thumb } from "@/components/ui/Thumb";
import { cn } from "@/lib/cn";
import { attributeToText, formatMoney } from "@/lib/format";

const MAX_CHIPS = 6;

export function ProductCard({
  product,
  currency,
  onEdit,
  index,
}: {
  product: ProductOut;
  currency: string;
  onEdit: () => void;
  index: number;
}) {
  const price = formatMoney(product.price_minor, currency);
  const attributes = Object.entries(product.attributes);
  const hidden = attributes.length - MAX_CHIPS;

  return (
    <article
      style={{ animationDelay: `${Math.min(index, 8) * 40}ms` }}
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-soft animate-enter",
        "transition-[transform,box-shadow,border-color] duration-200 hover:-translate-y-0.5 hover:border-brand-1/40 hover:shadow-lift",
        product.status === "draft" && "opacity-80",
      )}
    >
      <div className="relative">
        <Thumb
          src={product.image_url}
          alt={product.name}
          className="aspect-[4/3] size-auto w-full rounded-none ring-0"
        />
        <div className="absolute top-3 left-3">
          <Badge
            tone={product.status === "active" ? "success" : "neutral"}
            className="bg-surface-strong/90 shadow-soft backdrop-blur-md"
          >
            {product.status === "active" ? "Active" : "Draft"}
          </Badge>
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <h3 className="min-w-0 text-base font-semibold leading-snug break-words">{product.name}</h3>
          <p className="shrink-0 font-display text-lg font-bold">
            {price ?? <span className="text-sm font-normal text-fg-subtle">No price</span>}
          </p>
        </div>
        {product.description ? (
          <p className="line-clamp-2 text-sm text-fg-muted">{product.description}</p>
        ) : null}
        {attributes.length > 0 ? (
          <ul className="flex flex-wrap gap-1.5" aria-label="Attributes">
            {attributes.slice(0, MAX_CHIPS).map(([key, value]) => (
              <li key={key} className="rounded-lg bg-surface-muted px-2 py-1 text-xs ring-1 ring-border">
                <span className="text-fg-subtle">{key}</span>{" "}
                <span className="font-medium">{attributeToText(value)}</span>
              </li>
            ))}
            {hidden > 0 ? <li className="px-1 py-1 text-xs text-fg-subtle">+{hidden} more</li> : null}
          </ul>
        ) : null}
      </div>
      <button
        type="button"
        onClick={onEdit}
        aria-label={`Edit ${product.name}`}
        className={cn(
          "absolute top-3 right-3 grid size-9 cursor-pointer place-items-center rounded-xl bg-surface-strong/90 text-fg shadow-soft backdrop-blur",
          "transition-[opacity,transform,background-color] duration-200 hover:scale-105 hover:bg-surface-strong",
          "opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:focus-visible:opacity-100",
        )}
      >
        <Pencil className="size-4" aria-hidden />
      </button>
    </article>
  );
}
