import clsx from "clsx";
import { AlertTriangle, ShieldAlert } from "lucide-react";

import type { Device } from "@/lib/types";

export const HEALTH_COLOR = { critical: "var(--bad)", warning: "var(--accent)" } as const;

export function healthTitle(device: Pick<Device, "issues">): string {
  return device.issues.map((issue) => issue.message).join("\n");
}

export function HealthIcon({ device, className }: { device: Pick<Device, "health" | "issues" | "name">; className?: string }) {
  if (device.health === "ok") return null;
  return (
    <span
      role="img"
      aria-label={`${device.name} needs attention: ${device.issues.map((i) => i.message).join("; ")}`}
      title={healthTitle(device)}
      className={clsx("inline-flex shrink-0", className)}
      style={{ color: HEALTH_COLOR[device.health] }}
    >
      <AlertTriangle className="size-4" strokeWidth={2.2} />
    </span>
  );
}

export function HealthBanner({ device }: { device: Pick<Device, "health" | "issues"> }) {
  if (device.health === "ok") return null;
  const critical = device.health === "critical";
  return (
    <section
      role="alert"
      className={clsx(
        "flex gap-3 rounded-[14px] border px-5 py-4",
        critical ? "border-bad bg-[color-mix(in_srgb,var(--bad)_10%,var(--card))]" : "border-accent-line bg-accent-soft",
      )}
    >
      <ShieldAlert className={clsx("mt-0.5 size-5 shrink-0", critical ? "text-bad" : "text-accent-text")} aria-hidden />
      <div className="flex flex-col gap-1">
        <h2 className={clsx("text-[15px] font-semibold", critical ? "text-bad" : "text-accent-text")}>
          {critical ? "This device has a problem" : "This device needs attention"}
        </h2>
        <ul className="flex flex-col gap-0.5 text-sm text-text2">
          {device.issues.map((issue) => (
            <li key={`${issue.kind}-${issue.message}`} className="flex items-baseline gap-2">
              <span className="size-1.5 shrink-0 translate-y-[-2px] rounded-full" style={{ background: HEALTH_COLOR[issue.severity as "critical" | "warning"] }} />
              {issue.message}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
