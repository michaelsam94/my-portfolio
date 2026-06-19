import { useCallback, useEffect, useState } from "react";
import {
  applyTheme,
  getStoredTheme,
  getSystemTheme,
  initTheme,
  THEME_STORAGE_KEY,
  type Theme,
} from "../lib/theme";

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => initTheme());

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: light)");

    const handleChange = () => {
      if (!getStoredTheme()) {
        const next = getSystemTheme();
        setThemeState(next);
        applyTheme(next);
      }
    };

    media.addEventListener("change", handleChange);
    return () => media.removeEventListener("change", handleChange);
  }, []);

  const setTheme = useCallback((next: Theme) => {
    localStorage.setItem(THEME_STORAGE_KEY, next);
    applyTheme(next);
    setThemeState(next);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [setTheme, theme]);

  return { theme, setTheme, toggleTheme };
}
