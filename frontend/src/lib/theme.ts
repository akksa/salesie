import { useSyncExternalStore } from "react";

export type ThemePreference = "light" | "dark" | "system";

const STORAGE_KEY = "salesie-theme";
const QUERY = "(prefers-color-scheme: dark)";

function readPreference(): ThemePreference {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

function apply(preference: ThemePreference): void {
  const dark = preference === "dark" || (preference === "system" && window.matchMedia(QUERY).matches);
  document.documentElement.classList.toggle("dark", dark);
}

/*
 * Tiny shared store: the sidebar (and its toggle) is mounted twice — desktop rail
 * and mobile drawer — so both instances must read the same preference.
 */
let current: ThemePreference = readPreference();
const listeners = new Set<() => void>();

function setPreference(next: ThemePreference): void {
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    // Storage can be unavailable (private mode); the choice still applies for this session.
  }
  current = next;
  apply(next);
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  const media = window.matchMedia(QUERY);
  const onSystemChange = () => {
    if (current === "system") apply("system");
  };
  media.addEventListener("change", onSystemChange);
  return () => {
    listeners.delete(listener);
    media.removeEventListener("change", onSystemChange);
  };
}

/** Light/dark/system theme, persisted in localStorage and applied as a class on <html>. */
export function useTheme(): [ThemePreference, (next: ThemePreference) => void] {
  const preference = useSyncExternalStore(subscribe, () => current);
  return [preference, setPreference];
}
