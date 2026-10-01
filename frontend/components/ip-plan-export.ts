import type { Device, Group } from "@/lib/types";

function csvField(value: string | null | undefined): string {
  const text = value ?? "";
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function devicesCsv(devices: Device[], groups: Group[]): string {
  const rows = devices
    .filter((d) => d.access !== "pending")
    .map((d) => [d.name, d.mac, d.static_ip, groups.find((g) => g.id === d.group_id)?.name ?? ""].map(csvField).join(","));
  return ["name,mac,static_ip,group", ...rows].join("\n") + "\n";
}
