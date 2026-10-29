import { Menu, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router";
import { cn } from "@/lib/cn";
import { BrandMark, Sidebar } from "./Sidebar";

/** Inbox switches threads inside one page, so it keeps a stable key (no re-enter animation). */
function pageKey(pathname: string): string {
  return pathname.startsWith("/inbox") ? "/inbox" : pathname;
}

function MobileDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <div className="lg:hidden">
      <div
        aria-hidden
        onClick={onClose}
        className={cn(
          "fixed inset-0 z-40 bg-black/40 backdrop-blur-sm transition-opacity duration-300",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />
      <aside
        id="mobile-nav"
        aria-label="Navigation"
        inert={!open}
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-72 max-w-[85vw] border-r border-border bg-surface-strong shadow-lift",
          "transition-transform duration-300 ease-out",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close navigation"
          className="absolute top-5 right-3 grid size-9 cursor-pointer place-items-center rounded-xl text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg"
        >
          <X className="size-5" aria-hidden />
        </button>
        <Sidebar onNavigate={onClose} />
      </aside>
    </div>
  );
}

export function AppShell() {
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);

  return (
    <div className="min-h-dvh lg:pl-64">
      <a
        href="#main"
        className="sr-only z-[60] rounded-lg bg-surface-strong px-3 py-2 focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>

      <aside
        aria-label="Navigation"
        className="fixed inset-y-0 left-0 hidden w-64 border-r border-border bg-surface/60 backdrop-blur-xl lg:block"
      >
        <Sidebar />
      </aside>

      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-surface/80 px-4 backdrop-blur-xl lg:hidden">
        <BrandMark />
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          aria-label="Open navigation"
          aria-expanded={drawerOpen}
          aria-controls="mobile-nav"
          className="grid size-10 cursor-pointer place-items-center rounded-xl text-fg-muted transition-[background-color,color,transform] duration-200 hover:bg-surface-muted hover:text-fg active:scale-95"
        >
          <Menu className="size-5" aria-hidden />
        </button>
      </header>
      <MobileDrawer open={drawerOpen} onClose={closeDrawer} />

      <main id="main" className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-10 lg:py-10">
        <div key={pageKey(location.pathname)} className="animate-page">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
