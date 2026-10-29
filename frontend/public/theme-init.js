// Applies the saved/system colour theme before first paint to avoid a light flash in dark mode.
(() => {
  try {
    const pref = localStorage.getItem("salesie-theme");
    const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const dark = pref === "dark" || (pref !== "light" && systemDark);
    document.documentElement.classList.toggle("dark", dark);
  } catch {
    // localStorage can be blocked; the React theme hook will apply the theme on mount.
  }
})();
