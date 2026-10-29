import { cn } from "@/lib/cn";
import { linkify } from "@/lib/linkify";

/** Renders untrusted message text with http(s) URLs as safe external links. */
export function LinkifiedText({ text, linkClassName }: { text: string; linkClassName?: string }) {
  return (
    <>
      {linkify(text).map((segment, index) =>
        segment.kind === "link" ? (
          <a
            // biome-ignore lint/suspicious/noArrayIndexKey: segments are derived from immutable text
            key={index}
            href={segment.href}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(
              "break-all underline underline-offset-2 transition-opacity hover:opacity-80",
              linkClassName,
            )}
          >
            {segment.text}
          </a>
        ) : (
          // biome-ignore lint/suspicious/noArrayIndexKey: segments are derived from immutable text
          <span key={index}>{segment.text}</span>
        ),
      )}
    </>
  );
}
