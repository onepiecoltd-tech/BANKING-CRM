import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { vi } from "./locales/vi";

export type Lang = "vi" | "en";

function readStored(): Lang {
  try {
    if (typeof window !== "undefined") {
      const s = window.localStorage.getItem("crm-lang");
      if (s === "en" || s === "vi") return s;
    }
  } catch {
    /* storage unavailable */
  }
  return "vi";
}

// Module-level current language so `t()` can be used anywhere, including module-level constants.
// Read once when the bundle loads; switching language stores the choice and reloads the page.
let current: Lang = readStored();

/**
 * Translate. Two call styles:
 *   t("Dashboard")                 → English source key, looked up in the Vietnamese dictionary.
 *   t("Tổng khách hàng", "Total")  → Vietnamese-first text with an explicit English fallback.
 */
export function t(a: string, b?: string): string {
  if (current === "vi") return vi[a] ?? a;
  return b ?? a;
}

export function getLang(): Lang {
  return current;
}

type Ctx = { lang: Lang; setLang: (l: Lang) => void };
const I18nCtx = createContext<Ctx>({ lang: "vi", setLang: () => {} });

export function I18nProvider({ children }: { children: ReactNode }) {
  // Render the app only on the client: the language is only known there, so this avoids SSR/hydration mismatches.
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
    document.documentElement.lang = current;
  }, []);

  const setLang = (l: Lang) => {
    if (l === current) return;
    try {
      window.localStorage.setItem("crm-lang", l);
    } catch {
      /* ignore */
    }
    window.location.reload();
  };

  return <I18nCtx.Provider value={{ lang: current, setLang }}>{mounted ? children : null}</I18nCtx.Provider>;
}

export function useI18n() {
  return useContext(I18nCtx);
}

// ── VND / date helpers used by the corporate pages ──────────────────────────
export function fmtBn(bn: number | null | undefined, digits = 1): string {
  if (bn == null) return "—";
  const unit = current === "vi" ? " tỷ" : " bn";
  return new Intl.NumberFormat(current === "vi" ? "vi-VN" : "en-US", { maximumFractionDigits: digits }).format(bn) + unit;
}

export function fmtNum(n: number | null | undefined, digits = 0): string {
  if (n == null) return "—";
  return new Intl.NumberFormat(current === "vi" ? "vi-VN" : "en-US", { maximumFractionDigits: digits }).format(n);
}
