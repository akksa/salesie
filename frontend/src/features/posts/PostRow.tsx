import { ExternalLink, LoaderCircle, MessageCircle } from "lucide-react";
import type { PostOut, ProductOut } from "@/api/types";
import { ChannelIcon } from "@/components/ChannelIcon";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Thumb } from "@/components/ui/Thumb";
import { cn } from "@/lib/cn";
import { formatAbsolute, formatRelative } from "@/lib/format";
import { safeHttpUrl } from "@/lib/url";
import { useUpdatePost } from "./api";
import { ProductOptions, toProductId } from "./ProductSelect";

function LinkedProductSelect({ post, products }: { post: PostOut; products: ProductOut[] }) {
  const update = useUpdatePost();
  const selectId = `post-${post.id}-product`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={selectId} className="text-xs font-medium text-fg-subtle">
        Linked product
      </label>
      <div className="relative">
        <select
          id={selectId}
          value={post.product_id ?? ""}
          disabled={update.isPending}
          onChange={(e) => update.mutate({ id: post.id, body: { product_id: toProductId(e.target.value) } })}
          className={cn(
            "h-9 w-full cursor-pointer rounded-lg border bg-surface-strong pr-8 pl-2.5 text-sm",
            "transition-[border-color,box-shadow] duration-200 hover:border-border-strong focus:border-ring focus:outline-none focus:ring-4 focus:ring-ring/15",
            post.product_id === null
              ? "border-dashed border-border-strong text-fg-muted"
              : "border-border text-fg",
          )}
        >
          <ProductOptions products={products} emptyLabel="Not linked" />
        </select>
        {update.isPending ? (
          <LoaderCircle
            className="absolute top-2.5 right-7 size-4 animate-spin text-fg-subtle"
            aria-label="Saving"
          />
        ) : null}
      </div>
      {update.error ? <ErrorBanner error={update.error} className="mt-1 py-2 text-xs" /> : null}
    </div>
  );
}

export function PostRow({ post, products, index }: { post: PostOut; products: ProductOut[]; index: number }) {
  const permalink = safeHttpUrl(post.permalink);
  return (
    <li
      style={{ animationDelay: `${Math.min(index, 8) * 40}ms` }}
      className="grid grid-cols-[auto_1fr] gap-4 p-4 animate-enter transition-colors duration-200 hover:bg-surface-muted/50 sm:p-5 md:grid-cols-[auto_1fr_14rem]"
    >
      <Thumb src={post.image_url} alt={post.caption ?? "Post image"} className="size-16 sm:size-20" />
      <div className="min-w-0 space-y-2">
        <p className={cn("line-clamp-3 text-sm break-words", !post.caption && "italic text-fg-subtle")}>
          {post.caption || "No caption"}
        </p>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fg-muted">
          <span className="inline-flex items-center gap-1.5">
            <ChannelIcon channel={post.channel} size="sm" />
            <span className="font-mono">{post.external_id}</span>
          </span>
          <span
            className={cn(
              "inline-flex items-center gap-1 font-medium",
              post.engagement_count > 0 ? "text-brand-fg" : "text-fg-subtle",
            )}
          >
            <MessageCircle className="size-3.5" aria-hidden />
            {post.engagement_count} engagement{post.engagement_count === 1 ? "" : "s"}
          </span>
          <time dateTime={post.created_at} title={formatAbsolute(post.created_at)}>
            Added {formatRelative(post.created_at)}
          </time>
          {permalink ? (
            <a
              href={permalink}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-medium text-fg-muted underline-offset-2 transition-colors hover:text-brand-fg hover:underline"
            >
              View post <ExternalLink className="size-3" aria-hidden />
            </a>
          ) : null}
        </div>
      </div>
      <div className="col-span-2 md:col-span-1">
        <LinkedProductSelect post={post} products={products} />
      </div>
    </li>
  );
}
