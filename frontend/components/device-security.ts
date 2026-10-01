import type { Device, ServiceItem } from "@/lib/types";

export type RiskLevel = "High" | "Medium" | "Low" | "None";

export function riskLevel(services: ServiceItem[]): RiskLevel {
  const active = services.filter((s) => !s.muted);
  if (active.some((s) => s.risk === "high")) return "High";
  if (active.some((s) => s.risk === "warning")) return "Medium";
  if (services.length > 0) return "Low";
  return "None";
}

const RISK_ORDER = { high: 0, warning: 1, none: 2 } as const;

export function sortServices(services: ServiceItem[]): ServiceItem[] {
  return [...services].sort((a, b) => RISK_ORDER[a.risk] - RISK_ORDER[b.risk] || a.port - b.port);
}

function adviceFor(service: ServiceItem): string {
  const name = (service.service ?? "").toLowerCase();
  const where = `port ${service.port}/${service.proto}`;
  if (name === "telnet" || service.port === 23 || service.port === 2323) {
    return `Disable telnet (${where}): it sends passwords in clear text. Use SSH or the vendor app instead.`;
  }
  if (name === "ftp" || service.port === 21) return `Turn off FTP (${where}) or switch to SFTP.`;
  if (name === "upnp") return `Disable UPnP control (${where}) if nothing on the network needs it.`;
  if (name === "vnc" || service.port === 5900 || service.port === 5901) return `Protect or disable VNC (${where}).`;
  if (name === "ms-wbt-server" || service.port === 3389) return `Restrict remote desktop (${where}) to the devices that need it.`;
  const label = service.service ?? "this service";
  return service.risk === "high"
    ? `Close ${label} on ${where} unless you need it.`
    : `Check whether ${label} on ${where} needs to be reachable.`;
}

export function adviceList(device: Device, services: ServiceItem[], scanWindow: { start: string; end: string }): string[] {
  const tips: string[] = [];
  const risky = sortServices(services).filter((s) => s.risk !== "none" && !s.muted);
  const muted = services.filter((s) => s.risk !== "none" && s.muted).length;
  tips.push(...risky.map(adviceFor));
  if (muted) tips.push(`${muted} accepted risk${muted === 1 ? " is" : "s are"} muted: no alerts for ${muted === 1 ? "it" : "them"}.`);
  if (!device.last_scan_at) {
    tips.push(`Not scanned yet: press Scan now (scans run between ${scanWindow.start} and ${scanWindow.end}).`);
  } else if (risky.length === 0) {
    tips.push(services.length ? "No risky services found. Rescan after firmware updates." : "No open ports found. Nothing to do.");
  }
  if (device.access === "lan_only") tips.push("LAN only is active: the device reaches home devices but never the internet.");
  if (device.private_mac) tips.push("Private MAC: if the device changes it, Janus will see it as a new device again.");
  return tips;
}
