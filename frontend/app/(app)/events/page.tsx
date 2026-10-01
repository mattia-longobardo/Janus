"use client";

import { useCallback, useEffect, useState } from "react";

import { EventList } from "@/components/event-list";
import { Button, Card, Notice, PageHeader, inputClass } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { EVENT_TYPES } from "@/lib/events";
import type { EventItem } from "@/lib/types";

const PAGE = 50;

export default function EventsPage() {
  const [type, setType] = useState("");
  const [mac, setMac] = useState("");
  const [events, setEvents] = useState<EventItem[]>([]);
  const [error, setError] = useState<string>();
  const [more, setMore] = useState(false);

  const query = useCallback(
    (beforeId?: number) => {
      const params = new URLSearchParams({ limit: String(PAGE) });
      if (type) params.set("type", type);
      if (mac.trim()) params.set("mac", mac.trim());
      if (beforeId) params.set("before_id", String(beforeId));
      return `/events?${params}`;
    },
    [type, mac],
  );

  useEffect(() => {
    let cancelled = false;
    api
      .get<EventItem[]>(query())
      .then((page) => {
        if (cancelled) return;
        setEvents(page);
        setMore(page.length === PAGE);
        setError(undefined);
      })
      .catch((err) => !cancelled && setError(errorText(err)));
    return () => {
      cancelled = true;
    };
  }, [query]);

  async function loadMore() {
    const last = events.at(-1);
    if (!last) return;
    try {
      const page = await api.get<EventItem[]>(query(last.id));
      setEvents((current) => [...current, ...page]);
      setMore(page.length === PAGE);
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <>
      <PageHeader title="Event log" subtitle="everything Janus noticed or changed, newest first" />
      {error && <Notice tone="error">{error}</Notice>}
      <Card className="p-5">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row">
          <label className="sm:w-64">
            <span className="sr-only">Event type</span>
            <select className={inputClass} value={type} onChange={(e) => setType(e.target.value)}>
              <option value="">All events</option>
              {EVENT_TYPES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label className="sm:w-72">
            <span className="sr-only">MAC address</span>
            <input className={`${inputClass} font-mono`} placeholder="Filter by MAC" value={mac} onChange={(e) => setMac(e.target.value)} />
          </label>
        </div>
        <EventList events={events} />
        {more && (
          <Button className="mt-4" onClick={() => void loadMore()}>
            Load older events
          </Button>
        )}
      </Card>
    </>
  );
}
