"use client";

import Link from "next/link";

import { Card, PageHeader, SectionTitle } from "@/components/ui";
import { buildCells, lastOctet, rangeUsage } from "@/lib/ipplan";
import { useSettings } from "@/lib/settings-context";
import type { Device, Group } from "@/lib/types";
import { useResource } from "@/lib/use-resource";

export default function IpPlanPage() {
  const { settings } = useSettings();
  const devicesRes = useResource<Device[]>("/devices");
  const groupsRes = useResource<Group[]>("/groups");
  const devices = devicesRes.data ?? [];
  const groups = groupsRes.data ?? [];
  const cells = buildCells(groups, devices, settings.network.gateway);
  const qStart = lastOctet(settings.network.quarantine_start);
  const qEnd = lastOctet(settings.network.quarantine_end);
  const used = devices.filter((d) => d.static_ip).length;

  return (
    <>
      <PageHeader title="IP plan" subtitle={`${settings.network.subnet} · ${used} reserved · one range per group`} />
      <div className="grid gap-6 xl:grid-cols-[auto_1fr]">
        <Card className="overflow-x-auto p-4 lg:p-5">
          <div className="grid w-[640px] grid-cols-16 gap-1 lg:w-[760px]" role="grid" aria-label="Address map">
            {cells.map((cell) => {
              const quarantine = cell.octet >= qStart && cell.octet <= qEnd;
              const color = cell.group?.color;
              const style = cell.device && color
                ? { background: color, color: "#0E1113", borderColor: color }
                : color
                  ? { background: `${color}22`, borderColor: `${color}66` }
                  : undefined;
              return (
                <div
                  key={cell.octet}
                  role="gridcell"
                  title={
                    cell.device
                      ? `.${cell.octet} — ${cell.device.name}`
                      : cell.reserved
                        ? `.${cell.octet} — reserved`
                        : quarantine
                          ? `.${cell.octet} — quarantine pool`
                          : `.${cell.octet} — ${cell.group?.name ?? "unassigned"}`
                  }
                  className={`flex h-9 items-center justify-center rounded-md border font-mono text-[11px] lg:h-11 ${
                    quarantine && !color ? "border-dashed border-accent text-accent-text" : "border-line text-text2"
                  } ${cell.reserved ? "opacity-50" : ""}`}
                  style={style}
                >
                  {cell.octet}
                </div>
              );
            })}
          </div>
          <div className="mt-4 flex flex-wrap gap-5 text-xs text-muted">
            <span className="flex items-center gap-1.5">
              <span className="size-3.5 rounded bg-ok" />
              reserved for a device
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-3.5 rounded border border-line2" />
              free
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-3.5 rounded border border-dashed border-accent" />
              quarantine pool
            </span>
          </div>
        </Card>
        <Card className="p-5">
          <div className="mb-2 flex items-center justify-between">
            <SectionTitle>Ranges</SectionTitle>
            <Link href="/groups" className="text-sm text-muted underline">
              Edit groups
            </Link>
          </div>
          <ul>
            {groups.map((g) => {
              const usage = rangeUsage(g, devices);
              return (
                <li key={g.id} className="grid grid-cols-[14px_1fr_auto] items-center gap-3 border-b border-row py-2.5 last:border-0">
                  <span className="size-3 rounded-sm" style={{ background: g.color }} />
                  <span className="flex flex-col">
                    <span className="text-sm font-medium">{g.name}</span>
                    <span className="font-mono text-xs text-faint">
                      .{lastOctet(g.range_start)}–.{lastOctet(g.range_end)}
                    </span>
                  </span>
                  <span className="font-mono text-[13px] text-text2">
                    {usage.used}/{usage.total}
                  </span>
                </li>
              );
            })}
            <li className="grid grid-cols-[14px_1fr_auto] items-center gap-3 py-2.5">
              <span className="size-3 rounded-sm border border-dashed border-accent" />
              <span className="flex flex-col">
                <span className="text-sm font-medium">Quarantine (DHCP pool)</span>
                <span className="font-mono text-xs text-faint">
                  .{qStart}–.{qEnd}
                </span>
              </span>
              <span className="font-mono text-[13px] text-text2">{qEnd - qStart + 1}</span>
            </li>
          </ul>
        </Card>
      </div>
    </>
  );
}
