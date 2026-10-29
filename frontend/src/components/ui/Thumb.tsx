import { ImageOff } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";
import { safeHttpUrl } from "@/lib/url";

/** Square image thumbnail with a graceful fallback for missing/broken URLs. */
export function Thumb({
  src,
  alt,
  className,
}: {
  src: string | null | undefined;
  alt: string;
  className?: string;
}) {
  const url = safeHttpUrl(src);
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const showImage = url !== undefined && failedUrl !== url;
  return (
    <div
      className={cn(
        "relative grid size-12 shrink-0 place-items-center overflow-hidden rounded-xl bg-surface-muted ring-1 ring-border",
        className,
      )}
    >
      {showImage ? (
        <img
          src={url}
          alt={alt}
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setFailedUrl(url)}
          className="size-full object-cover"
        />
      ) : (
        <ImageOff
          className="size-[35%] max-h-10 max-w-10 text-fg-subtle"
          aria-label={alt ? `${alt} (no image)` : "No image"}
        />
      )}
    </div>
  );
}
