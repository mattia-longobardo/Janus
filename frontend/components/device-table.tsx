"use client";

import Link from "next/link";

import { Badge, StatusDot } from "@/components/ui";
import { ACCESS_LABELS, deviceIp, formatDateTime, relativeTime } from "@/lib/format";
import { useSettings } from "@/lib/settings-context";
import type { Device, Group } from "@/lib/types";

const HEADERS = ["Status", "Name", "Group", "IP", "MAC", "Vendor", "Access", "Seen"];

export function DeviceTable({ devices, groups }: { devices: Device[]; groups: Group[] }) {
  const { settings } = useSettings();
  if (devices.length === 0) return <p className="px-5 py-8 text-center text-sm text-muted">No devices match.</p>;
  const groupName = (id: number | null) => groups.find((g) => g.id === id)?.name ?? "—";
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] text-sm">
        <thead>
          <tr className="border-y border-line text-left text-xs uppercase tracking-wider text-faint">
            {HEADERS.map((header) => (
              <th key={header} scope="col" className="px-5 py-2.5 font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {devices.map((d) => (
            <tr key={d.id} className="border-b border-row hover:bg-card2">
              <td className="px-5 py-2.5">
                <span className="flex items-center gap-2 text-text2">
                  <StatusDot online={d.online} />
                  {d.online ? "Online" : "Offline"}
                </span>
              </td>
              <td className="px-5 py-2.5 font-medium">
                <span className="flex flex-wrap items-center gap-2">
                  <Link href={`/devices/${d.id}`} className="hover:underline">
                    {d.name}
                  </Link>
                  {d.private_mac && <Badge tone="accent">private MAC</Badge>}
                </span>
              </td>
              <td className="px-5 py-2.5 text-muted">{groupName(d.group_id)}</td>
              <td className="px-5 py-2.5 font-mono text-[13px]">{deviceIp(d) ?? "—"}</td>
              <td className="px-5 py-2.5 font-mono text-[13px] text-muted">{d.mac ?? "—"}</td>
              <td className="max-w-48 truncate px-5 py-2.5 text-muted">{d.vendor ?? "—"}</td>
              <td className="px-5 py-2.5 text-muted">{ACCESS_LABELS[d.access]}</td>
              <td className="px-5 py-2.5 font-mono text-xs text-faint" title={formatDateTime(d.last_seen, settings.timezone, settings.time_format)}>
                {relativeTime(d.last_seen)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
