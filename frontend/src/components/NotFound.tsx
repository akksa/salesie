import { Compass } from "lucide-react";
import { Link } from "react-router";
import { EmptyState } from "@/components/ui/EmptyState";

export function NotFound() {
  return (
    <EmptyState
      icon={<Compass className="size-6" aria-hidden />}
      title="Nothing here"
      action={
        <Link
          to="/contacts"
          className="brand-gradient inline-flex h-10 items-center rounded-xl px-4 text-sm font-medium text-white shadow-soft transition-[box-shadow,filter] duration-200 hover:shadow-lift hover:brightness-110"
        >
          Back to contacts
        </Link>
      }
    >
      That page doesn't exist. It may have moved, or the link was mistyped.
    </EmptyState>
  );
}
