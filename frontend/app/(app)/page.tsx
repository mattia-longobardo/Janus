"use client";

import clsx from "clsx";
import Link from "next/link";

import { DeviceTable } from "@/components/device-table";
import { EventList } from "@/components/event-list";
import { Card, Notice, PageHeader, SectionTitle } from "@/components/ui";
import { filterDevices } from "@/lib/filter";
import { useSettings } from "@/lib/settings-context";
import type { Device, EventItem, Group } from "@/lib/types";
import { useResource } from "@/lib/use-resource";

export default function OverviewPage() {
  const { settings } = useSettings();
  const devicesRes = useResource<Device[]>("/devices", { refreshMs: 30_000 });
  const groupsRes = useResource<Group[]>("/groups");
  const eventsRes = useResource<EventItem[]>("/events?limit=8", { refreshMs: 30_000 });
  const devices = devicesRes.data ?? [];
  const approved = devices.filter((d) => d.access === "authorized" || d.access === "lan_only");
  const pending = devices.filter((d) => d.access === "pending");
  const blocked = devices.filter((d) => d.access === "blocked");
  const stats = [
    { label: "Approved", value: approved.length, note: `${approved.filter((d) => d.online).length} online`, tone: "text-text" },
    { label: "Online now", value: devices.filter((d) => d.online).length, note: `${approved.filter((d) => !d.online && d.last_seen).length} approved offline`, tone: "text-ok" },
    { label: "Pending", value: pending.length, note: settings.sync_mode === "apply" ? "in quarantine" : "detected (dry-run)", tone: "text-accent-text" },
    { label: "Blocked", value: blocked.length, note: "no network", tone: "text-bad" },
  ];

  return (
    <>
      <PageHeader
        title="Home network"
        subtitle={`${settings.network.subnet} · gateway ${settings.network.gateway} · DNS/DHCP Pi-hole`}
        actions={<Link href="/devices" className="text-sm text-muted underline">All devices</Link>}
      />
      {devicesRes.error && <Notice tone="error">{devicesRes.error}</Notice>}
      <section aria-label="Summary" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label} className="flex flex-col gap-1.5 p-5">
            <span className="text-[13px] text-muted">{stat.label}</span>
            <span className={clsx("font-display text-4xl font-bold leading-none", stat.tone)}>{stat.value}</span>
            <span className="font-mono text-xs text-faint">{stat.note}</span>
          </Card>
        ))}
      </section>

      {pending.length > 0 && (
        <Card className="mt-6 overflow-hidden border-accent-line">
          <div className="flex flex-wrap items-center justify-between gap-2 bg-accent-soft px-5 py-4">
            <SectionTitle>New devices waiting for approval</SectionTitle>
            <Link href="/pending" className="text-sm font-semibold text-accent-text">
              Review all
            </Link>
          </div>
          <ul>
            {pending.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center gap-x-6 gap-y-1 border-t border-line px-5 py-3.5">
                <span className="font-semibold">{d.name}</span>
                <span className="font-mono text-[13px] text-text2">{d.mac}</span>
                <span className="font-mono text-[13px] text-muted">{d.last_ip ?? "—"}</span>
                <span className="text-[13px] text-muted">{d.vendor ?? (d.private_mac ? "Private MAC" : "Unknown vendor")}</span>
                <Link href={`/pending#${d.id}`} className="ml-auto text-sm font-semibold text-accent-text">
                  Approve…
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="mt-6 grid gap-6 xl:grid-cols-[2fr_1fr]">
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4">
            <SectionTitle>Approved devices</SectionTitle>
            <span className="font-mono text-xs text-faint">{approved.length} total</span>
          </div>
          <DeviceTable devices={filterDevices(approved, { query: "", groupId: "all", access: "all" }).slice(0, 15)} groups={groupsRes.data ?? []} />
        </Card>
        <Card className="p-5">
          <div className="mb-3 flex items-center justify-between">
            <SectionTitle>Recent events</SectionTitle>
            <Link href="/events" className="text-sm text-muted underline">
              Event log
            </Link>
          </div>
          <EventList events={eventsRes.data ?? []} />
        </Card>
      </div>
    </>
  );
}
