"use client";

import { Checkbox } from "@/components/ui";
import type { Rule } from "@/lib/types";

const HINTS: Record<string, string> = {
  "device.new": "Always delivered, even in quiet hours",
  "device.offline": "Muted during maintenance windows",
  "infra.down": "Muted during maintenance windows",
  "infra.up": "Only after an outage alert was delivered",
  "device.ip_mismatch": "A device uses an address other than its reservation",
  "security.risky_service": "Telnet, FTP, unauthenticated web UIs and similar",
  "security.new_port": "Found by the scheduled port scan",
};

const GRID = "grid grid-cols-[1fr_72px_72px] items-center gap-3 sm:grid-cols-[1fr_90px_90px]";
const HEAD = "text-center text-xs font-medium uppercase tracking-[.06em] text-faint";

export function RulesTable({ rules, onChange }: { rules: Rule[]; onChange: (rule: Rule) => void }) {
  return (
    <div>
      <div className={`${GRID} border-b border-line pb-2.5`}>
        <h2 className="font-display text-[19px] font-bold">Events</h2>
        <span className={HEAD}>Email</span>
        <span className={HEAD}>Gotify</span>
      </div>
      {rules.map((rule) => (
        <div key={rule.event_type} className={`${GRID} border-b border-row py-3 last:border-0`}>
          <span className="flex flex-col gap-0.5">
            <span className="text-sm">{rule.label}</span>
            {HINTS[rule.event_type] && <span className="text-xs text-faint">{HINTS[rule.event_type]}</span>}
          </span>
          {(["email", "gotify"] as const).map((channel) => (
            <span key={channel} className="flex justify-center">
              <Checkbox
                aria-label={`${rule.label} ${channel === "email" ? "email" : "Gotify"}`}
                checked={rule[channel]}
                onChange={(e) => onChange({ ...rule, [channel]: e.target.checked })}
              />
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}
