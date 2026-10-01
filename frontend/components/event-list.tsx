"use client";

import { describeEvent } from "@/lib/events";
import { formatDateTime } from "@/lib/format";
import { useSettings } from "@/lib/settings-context";
import type { EventItem } from "@/lib/types";

export function EventList({ events }: { events: EventItem[] }) {
  const { settings } = useSettings();
  if (events.length === 0) return <p className="text-sm text-muted">No events yet.</p>;
  return (
    <ol className="flex flex-col">
      {events.map((event) => (
        <li key={event.id} className="grid grid-cols-[96px_1fr] gap-3 border-b border-row py-2.5 last:border-0">
          <span className="font-mono text-xs text-faint">{formatDateTime(event.ts, settings.timezone, settings.time_format)}</span>
          <span className="flex min-w-0 flex-col gap-0.5">
            <span className="text-sm text-text2">{describeEvent(event)}</span>
            {event.mac && <span className="font-mono text-[11px] text-faint">{event.mac}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}
