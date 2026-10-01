"use client";

import clsx from "clsx";
import { useEffect, useState } from "react";

import { THEME_EVENT, type ThemeChoice, applyTheme, readTheme, resolvedTheme } from "@/lib/theme";

const CHOICES: ThemeChoice[] = ["system", "light", "dark"];

export function ThemeToggle() {
  const [choice, setChoice] = useState<ThemeChoice>(() => (typeof window === "undefined" ? "system" : readTheme()));
  useEffect(() => setChoice(readTheme()), []);
  return (
    <div role="group" aria-label="Theme" className="inline-flex gap-0.5 rounded-lg border border-line bg-row p-1">
      {CHOICES.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={choice === option}
          onClick={() => {
            applyTheme(option);
            setChoice(option);
          }}
          className={clsx(
            "h-9 rounded-md px-4 text-sm font-medium capitalize",
            choice === option ? "bg-card text-text shadow-sm" : "text-muted",
          )}
        >
          {option}
        </button>
      ))}
    </div>
  );
}

export function useResolvedTheme(): "light" | "dark" {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  useEffect(() => {
    const update = () => setTheme(resolvedTheme());
    update();
    window.addEventListener(THEME_EVENT, update);
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    media?.addEventListener?.("change", update);
    return () => {
      window.removeEventListener(THEME_EVENT, update);
      media?.removeEventListener?.("change", update);
    };
  }, []);
  return theme;
}
