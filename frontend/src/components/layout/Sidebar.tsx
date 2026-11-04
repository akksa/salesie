import {
  ChartColumn,
  FlaskConical,
  Images,
  Inbox,
  type LucideIcon,
  Settings,
  ShoppingBag,
  SquareKanban,
  Users,
} from "lucide-react";
import { NavLink, useLocation } from "react-router";
import { AgentStatusCard } from "@/features/agent/AgentStatusCard";
import { usePipelineNeedsOwner } from "@/features/pipeline/api";
import { useAppConfig, useBusiness } from "@/features/settings/api";
import { cn } from "@/lib/cn";
import { ThemeToggle } from "./ThemeToggle";

interface NavItem {
  to: string;
  label: string;
  Icon: LucideIcon;
  /** Extra path prefixes that count as this item (e.g. the deal drawer belongs to Pipeline). */
  alsoActive?: string[];
}

const PRIMARY_NAV: NavItem[] = [
  { to: "/", label: "Pipeline", Icon: SquareKanban, alsoActive: ["/deals"] },
  { to: "/inbox", label: "Inbox", Icon: Inbox },
  { to: "/contacts", label: "Contacts", Icon: Users },
  { to: "/insights", label: "Insights", Icon: ChartColumn },
  { to: "/catalog", label: "Catalog", Icon: ShoppingBag },
  { to: "/posts", label: "Posts", Icon: Images },
];

const SIMULATOR_NAV: NavItem = { to: "/simulator", label: "Simulator", Icon: FlaskConical };
const SETTINGS_NAV: NavItem = { to: "/settings", label: "Settings", Icon: Settings };

export function BrandMark({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <span
        aria-hidden
        className="brand-gradient grid size-9 place-items-center rounded-xl font-display text-lg font-bold text-white shadow-soft"
      >
        S
      </span>
      <span className="font-display text-xl font-bold tracking-tight">Salesie</span>
    </span>
  );
}

function CountBadge({ count, label }: { count: number; label: string }) {
  return (
    <span
      title={label}
      className="ml-auto inline-flex min-w-5 items-center justify-center rounded-full bg-amber-500 px-1.5 text-[11px] font-bold text-amber-950 tabular-nums animate-enter"
    >
      {count}
      <span className="sr-only"> {label}</span>
    </span>
  );
}

function NavRow({
  item,
  onNavigate,
  badge = 0,
}: {
  item: NavItem;
  onNavigate?: (() => void) | undefined;
  badge?: number;
}) {
  const { pathname } = useLocation();
  const extra = item.alsoActive?.some((prefix) => pathname.startsWith(prefix)) ?? false;
  return (
    <li>
      <NavLink
        to={item.to}
        end={item.to === "/"}
        onClick={onNavigate}
        aria-current={extra ? "page" : undefined}
        className={({ isActive: routeActive }) => {
          const isActive = routeActive || extra;
          return cn(
            "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium",
            "transition-[background-color,color,transform] duration-200 hover:translate-x-0.5",
            isActive
              ? "bg-surface-strong text-fg shadow-soft ring-1 ring-border"
              : "text-fg-muted hover:bg-surface-muted hover:text-fg",
          );
        }}
      >
        {({ isActive: routeActive }) => {
          const isActive = routeActive || extra;
          return (
            <>
              <span
                aria-hidden
                className={cn(
                  "absolute inset-y-2 left-0 w-1 rounded-full brand-gradient transition-opacity duration-200",
                  isActive ? "opacity-100" : "opacity-0",
                )}
              />
              <item.Icon
                aria-hidden
                className={cn(
                  "size-[18px] transition-colors duration-200",
                  isActive ? "text-brand-fg" : "text-fg-subtle group-hover:text-fg",
                )}
              />
              {item.label}
              {badge > 0 ? (
                <CountBadge count={badge} label={badge === 1 ? "chat needs you" : "chats need you"} />
              ) : null}
            </>
          );
        }}
      </NavLink>
    </li>
  );
}

/** Navigation column, shared by the desktop rail and the mobile drawer. */
export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const appConfig = useAppConfig();
  const business = useBusiness();
  const needsOwner = usePipelineNeedsOwner();
  const tools = appConfig.data?.simulator_enabled ? [SIMULATOR_NAV, SETTINGS_NAV] : [SETTINGS_NAV];

  return (
    <div className="flex h-full flex-col gap-6 px-4 py-5">
      <div className="px-1">
        <BrandMark />
        <p className="mt-2 truncate text-xs text-fg-subtle" title={business.data?.name}>
          {business.data?.name ?? " "}
        </p>
      </div>

      <nav aria-label="Main" className="flex flex-1 flex-col gap-6">
        <ul className="flex flex-col gap-1">
          {PRIMARY_NAV.map((item) => (
            <NavRow
              key={item.to}
              item={item}
              onNavigate={onNavigate}
              badge={item.to === "/" ? (needsOwner.data ?? 0) : 0}
            />
          ))}
        </ul>
        <div>
          <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-fg-subtle">
            Tools
          </p>
          <ul className="flex flex-col gap-1">
            {tools.map((item) => (
              <NavRow key={item.to} item={item} onNavigate={onNavigate} />
            ))}
          </ul>
        </div>
      </nav>

      <div className="space-y-3">
        <AgentStatusCard />
        <p className="flex items-center gap-2 px-1 text-xs text-fg-subtle" title="Updates every 3 seconds">
          <span className="relative flex size-2">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-500 opacity-60 motion-reduce:hidden" />
            <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
          </span>
          Live
        </p>
        <ThemeToggle />
      </div>
    </div>
  );
}
