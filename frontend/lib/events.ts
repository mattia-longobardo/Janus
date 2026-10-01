import { ACCESS_LABELS } from "@/lib/format";
import type { Access, EventItem } from "@/lib/types";

export const EVENT_TYPES = [
  "device.new", "device.approved", "device.blocked", "device.updated", "device.deleted", "device.offline", "device.ip_mismatch",
  "device.private_mac", "device.gateway", "ip.conflict", "infra.down", "infra.up", "sync.applied", "sync.failed",
  "security.new_port", "security.risky_service", "scan.completed", "scan.failed", "maintenance.start",
  "maintenance.end", "notify.test", "notify.failed", "import.csv",
];

const SERVICES: Record<string, string> = { pihole: "Pi-hole", sentinel: "Scanner" };

export function describeEvent(event: Pick<EventItem, "type" | "payload">): string {
  const p = event.payload as Record<string, any>;
  switch (event.type) {
    case "device.new":
      return `New device ${p.hostname ? `${p.hostname} ` : ""}on ${p.ip ?? "no IP yet"}`;
    case "device.approved":
      return `Approved ${p.name} → ${p.ip} (${ACCESS_LABELS[p.access as Access] ?? p.access})`;
    case "device.blocked":
      return `Blocked ${p.name}`;
    case "device.deleted":
      return `Deleted ${p.name}${p.ip ? ` (${p.ip})` : ""}`;
    case "device.updated":
      return `Updated ${Object.keys(p.changes ?? {}).join(", ") || "device"}`;
    case "device.offline":
      return `${p.name} offline for more than ${p.hours} h`;
    case "device.ip_mismatch":
      return `${p.name} uses ${p.ip}, reserved ${p.expected}`;
    case "device.private_mac":
      return `Private MAC looks like ${p.previous_name}`;
    case "device.gateway":
      return "Gateway registered";
    case "ip.conflict":
      return `IP conflict on ${p.ip}`;
    case "infra.down":
      return `${SERVICES[p.service] ?? p.service} unreachable`;
    case "infra.up":
      return `${SERVICES[p.service] ?? p.service} reachable again`;
    case "sync.applied":
      return `Pi-hole reservations: +${(p.added ?? []).length} −${(p.removed ?? []).length}`;
    case "sync.failed":
      return `Pi-hole refused ${(p.failed ?? []).length} reservation(s)`;
    case "security.new_port":
      return `New open port ${p.port}/${p.proto}`;
    case "security.risky_service": {
      const ports: { port: number }[] = p.ports ?? (p.port ? [{ port: p.port }] : []);
      return ports.length > 1
        ? `Risky services on ports ${ports.map((x) => x.port).join(", ")}`
        : `Risky service on port ${ports[0]?.port ?? "?"}`;
    }
    case "scan.completed":
      return `Scan finished: ${p.open_ports} open port(s)`;
    case "scan.failed":
      return `Scan failed: ${p.error}`;
    case "maintenance.start":
      return "Maintenance window started";
    case "maintenance.end":
      return "Maintenance window ended";
    case "notify.test":
      return `Test notification (${p.channel})`;
    case "notify.failed":
      return "Notification could not be delivered";
    case "import.csv":
      return `CSV import: ${p.devices_created ?? 0} created, ${p.devices_updated ?? 0} updated`;
    default:
      return event.type;
  }
}
