import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type ThemeAppearance = "light" | "dark";

const STORAGE_KEY = "clash-tracker-appearance";

type ThemePreferenceContextValue = {
  appearance: ThemeAppearance;
  setAppearance: (next: ThemeAppearance) => void;
  toggleAppearance: () => void;
};

const ThemePreferenceContext = createContext<ThemePreferenceContextValue | null>(null);

function readStoredAppearance(): ThemeAppearance {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === "light") return "light";
  } catch {
    /* ignore */
  }
  return "dark";
}

export function ThemePreferenceProvider({ children }: { children: ReactNode }) {
  const [appearance, setAppearanceState] = useState<ThemeAppearance>(() => readStoredAppearance());

  const setAppearance = useCallback((next: ThemeAppearance) => {
    setAppearanceState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  }, []);

  const toggleAppearance = useCallback(() => {
    setAppearance(appearance === "dark" ? "light" : "dark");
  }, [appearance, setAppearance]);

  const value = useMemo(
    () => ({ appearance, setAppearance, toggleAppearance }),
    [appearance, setAppearance, toggleAppearance],
  );

  return (
    <ThemePreferenceContext.Provider value={value}>{children}</ThemePreferenceContext.Provider>
  );
}

export function useThemePreference() {
  const ctx = useContext(ThemePreferenceContext);
  if (!ctx) {
    throw new Error("useThemePreference must be used within ThemePreferenceProvider");
  }
  return ctx;
}
