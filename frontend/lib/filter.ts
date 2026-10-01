import { deviceIp, ipSortKey } from "@/lib/format";
import type { Access, Device } from "@/lib/types";

export interface DeviceFilter {
  query: string;
  groupId: number | "all";
  access: Access | "all";
}

export function filterDevices(devices: Device[], filter: DeviceFilter): Device[] {
  const query = filter.query.trim().toLowerCase();
  return devices
    .filter((d) => filter.groupId === "all" || d.group_id === filter.groupId)
    .filter((d) => filter.access === "all" || d.access === filter.access)
    .filter((d) => {
      if (!query) return true;
      return [d.name, d.hostname, d.static_ip, d.last_ip, d.mac, d.vendor, d.dhcp_hostname]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query));
    })
    .sort((a, b) => ipSortKey(deviceIp(a)) - ipSortKey(deviceIp(b)) || a.name.localeCompare(b.name));
}
