"use client";

import { useEffect, useState } from "react";

export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}

export function nextScanIn(lastSweepAt: string | null, intervalS: number, now: number): string | null {
  if (!lastSweepAt || intervalS <= 0) return null;
  const due = Date.parse(lastSweepAt) + intervalS * 1000;
  const seconds = Math.round((due - now) / 1000);
  if (seconds <= 0) return "scanning…";
  return seconds < 90 ? `next in ${seconds} s` : `next in ${Math.round(seconds / 60)} min`;
}
