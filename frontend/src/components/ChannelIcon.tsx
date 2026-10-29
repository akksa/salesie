import type { Channel } from "@/api/types";
import { cn } from "@/lib/cn";

export const CHANNEL_LABEL: Record<Channel, string> = {
  instagram: "Instagram",
  whatsapp: "WhatsApp",
  facebook: "Facebook",
  messenger: "Messenger",
};

const CHANNEL_BG: Record<Channel, string> = {
  instagram: "bg-linear-to-br from-amber-400 via-pink-500 to-violet-600",
  whatsapp: "bg-emerald-500",
  facebook: "bg-blue-600",
  messenger: "bg-linear-to-br from-sky-500 via-violet-500 to-pink-500",
};

/** Simplified, hand-drawn glyphs (not official logos) so we don't depend on brand icon packs. */
function Glyph({ channel }: { channel: Channel }) {
  switch (channel) {
    case "instagram":
      return (
        <>
          <rect x="5" y="5" width="14" height="14" rx="4.5" />
          <circle cx="12" cy="12" r="3.2" />
          <circle cx="16.3" cy="7.7" r="0.6" fill="currentColor" />
        </>
      );
    case "whatsapp":
      return (
        <>
          <path d="M5.5 18.5l1-3.4A7 7 0 1 1 9 17.6z" />
          <path
            d="M9.6 9.4c.2 1.9 2.6 4.4 4.8 4.9l.9-1.1-1.3-.8-.6.5c-.8-.4-1.6-1.2-2-2l.5-.6-.8-1.3z"
            fill="currentColor"
            stroke="none"
          />
        </>
      );
    case "facebook":
      return (
        <path d="M13.5 20v-7h2.4l.4-2.8h-2.8V8.6c0-.8.3-1.4 1.4-1.4h1.5V4.7a19 19 0 0 0-2.2-.1c-2.2 0-3.7 1.3-3.7 3.8v1.8H8V13h2.5v7" />
      );
    case "messenger":
      return (
        <>
          <path d="M12 4.5c-4.3 0-7.5 3.1-7.5 7 0 2.1.9 3.9 2.5 5.2v2.8l2.6-1.4c.8.2 1.6.4 2.4.4 4.3 0 7.5-3.1 7.5-7s-3.2-7-7.5-7z" />
          <path d="M7.8 13.6l2.6-2.8 1.7 1.6 2.4-1.6-2.6 2.8-1.7-1.6z" fill="currentColor" />
        </>
      );
  }
}

export function ChannelIcon({
  channel,
  className,
  size = "md",
}: {
  channel: Channel;
  className?: string;
  size?: "sm" | "md";
}) {
  const label = CHANNEL_LABEL[channel];
  return (
    <span
      role="img"
      aria-label={label}
      title={label}
      className={cn(
        "inline-grid shrink-0 place-items-center rounded-full text-white shadow-sm ring-2 ring-surface-strong",
        size === "sm" ? "size-5" : "size-6",
        CHANNEL_BG[channel],
        className,
      )}
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className={size === "sm" ? "size-3.5" : "size-4"}
      >
        <Glyph channel={channel} />
      </svg>
    </span>
  );
}

/** Overlapping stack of the distinct channels a contact is reachable on. */
export function ChannelStack({ channels }: { channels: Channel[] }) {
  const unique = [...new Set(channels)];
  if (unique.length === 0) return <span className="text-xs text-fg-subtle">—</span>;
  return (
    <span className="inline-flex -space-x-1.5">
      {unique.map((channel) => (
        <ChannelIcon key={channel} channel={channel} size="sm" />
      ))}
    </span>
  );
}
