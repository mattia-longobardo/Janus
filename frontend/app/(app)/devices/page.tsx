"use client";

import clsx from "clsx";
import { Search } from "lucide-react";
import { useMemo, useState } from "react";

import { DeviceTable } from "@/components/device-table";
import { Card, Notice, PageHeader, inputClass } from "@/components/ui";
import { filterDevices } from "@/lib/filter";
import { ACCESS_LABELS } from "@/lib/format";
import type { Access, Device, Group } from "@/lib/types";
import { useResource } from "@/lib/use-resource";

export default function DevicesPage() {
  const devicesRes = useResource<Device[]>("/devices", { refreshMs: 30_000 });
  const groupsRes = useResource<Group[]>("/groups");
  const [query, setQuery] = useState("");
  const [groupId, setGroupId] = useState<number | "all">("all");
  const [access, setAccess] = useState<Access | "all">("all");
  const groups = groupsRes.data ?? [];
  const devices = devicesRes.data ?? [];
  const filtered = useMemo(() => filterDevices(devices, { query, groupId, access }), [devices, query, groupId, access]);

  return (
    <>
      <PageHeader title="Devices" subtitle={`${devices.length} known · ${devices.filter((d) => d.online).length} online`} />
      {devicesRes.error && <Notice tone="error">{devicesRes.error}</Notice>}
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-3 px-5 py-4 lg:flex-row lg:items-center">
          <label className="flex h-11 items-center gap-2 rounded-lg border border-line2 bg-bg px-3 lg:w-80">
            <Search className="size-4 text-faint" aria-hidden />
            <span className="sr-only">Search devices</span>
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Name, IP, MAC or vendor"
              className="w-full bg-transparent text-sm outline-none"
            />
          </label>
          <label className="lg:w-52">
            <span className="sr-only">Access</span>
            <select className={inputClass} value={access} onChange={(e) => setAccess(e.target.value as Access | "all")}>
              <option value="all">Any access</option>
              {(Object.keys(ACCESS_LABELS) as Access[]).map((key) => (
                <option key={key} value={key}>
                  {ACCESS_LABELS[key]}
                </option>
              ))}
            </select>
          </label>
          <div className="flex flex-wrap gap-2 lg:ml-auto">
            {[{ id: "all" as const, name: "All" }, ...groups].map((g) => (
              <button
                key={g.id}
                type="button"
                aria-pressed={groupId === g.id}
                onClick={() => setGroupId(g.id)}
                className={clsx(
                  "h-9 rounded-full border px-3 text-[13px]",
                  groupId === g.id ? "border-inv-bg bg-inv-bg text-inv-fg" : "border-line2 text-text2",
                )}
              >
                {g.name}
              </button>
            ))}
          </div>
        </div>
        <DeviceTable devices={filtered} groups={groups} />
      </Card>
    </>
  );
}
