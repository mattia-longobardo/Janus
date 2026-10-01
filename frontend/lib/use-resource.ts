"use client";

import { useCallback, useEffect, useState } from "react";

import { CHANGED_EVENT, api, errorText } from "@/lib/api";

export function useResource<T>(path: string | null, options: { refreshMs?: number } = {}) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(Boolean(path));

  const reload = useCallback(async () => {
    if (!path) return;
    try {
      setData(await api.get<T>(path));
      setError(undefined);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    void reload();
    const onChange = () => void reload();
    const onVisible = () => {
      if (document.visibilityState === "visible") void reload();
    };
    window.addEventListener(CHANGED_EVENT, onChange);
    window.addEventListener("focus", onChange);
    document.addEventListener("visibilitychange", onVisible);
    const id = options.refreshMs ? window.setInterval(() => void reload(), options.refreshMs) : undefined;
    return () => {
      window.removeEventListener(CHANGED_EVENT, onChange);
      window.removeEventListener("focus", onChange);
      document.removeEventListener("visibilitychange", onVisible);
      if (id !== undefined) window.clearInterval(id);
    };
  }, [reload, options.refreshMs]);

  return { data, error, loading, reload, setData };
}
