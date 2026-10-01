"use client";

import { useCallback, useEffect, useState } from "react";

import { api, errorText } from "@/lib/api";

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
    if (!options.refreshMs) return;
    const id = window.setInterval(() => void reload(), options.refreshMs);
    return () => window.clearInterval(id);
  }, [reload, options.refreshMs]);

  return { data, error, loading, reload, setData };
}
