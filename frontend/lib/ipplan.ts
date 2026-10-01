import type { Device, Group } from "@/lib/types";

export interface Cell {
  octet: number;
  group: Group | null;
  device: Device | null;
  reserved: boolean;
}

export function lastOctet(ip: string): number {
  return Number(ip.split(".")[3]);
}

export function buildCells(groups: Group[], devices: Device[], gatewayIp: string): Cell[] {
  const byOctet = new Map<number, Device>();
  for (const device of devices) {
    if (device.static_ip) byOctet.set(lastOctet(device.static_ip), device);
  }
  const gateway = lastOctet(gatewayIp);
  return Array.from({ length: 256 }, (_, octet) => ({
    octet,
    group: groups.find((g) => lastOctet(g.range_start) <= octet && octet <= lastOctet(g.range_end)) ?? null,
    device: byOctet.get(octet) ?? null,
    reserved: octet === 0 || octet === 255 || octet === gateway,
  }));
}

export function rangeUsage(group: Group, devices: Device[]): { used: number; total: number } {
  const start = lastOctet(group.range_start);
  const end = lastOctet(group.range_end);
  const used = devices.filter((d) => d.static_ip && lastOctet(d.static_ip) >= start && lastOctet(d.static_ip) <= end).length;
  return { used, total: end - start + 1 };
}
