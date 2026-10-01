"use client";

import type { Rule } from "@/lib/types";

export function RulesTable({ rules, onChange }: { rules: Rule[]; onChange: (rule: Rule) => void }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs uppercase tracking-wider text-faint">
            <th className="py-2 font-medium">Event</th>
            <th className="w-24 py-2 text-center font-medium">Email</th>
            <th className="w-24 py-2 text-center font-medium">Gotify</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((rule) => (
            <tr key={rule.event_type} className="border-b border-row">
              <td className="py-3">{rule.label}</td>
              {(["email", "gotify"] as const).map((channel) => (
                <td key={channel} className="py-3 text-center">
                  <input
                    type="checkbox"
                    className="size-5 accent-[var(--accent)]"
                    aria-label={`${rule.label} by ${channel === "email" ? "email" : "Gotify"}`}
                    checked={rule[channel]}
                    onChange={(e) => onChange({ ...rule, [channel]: e.target.checked })}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
