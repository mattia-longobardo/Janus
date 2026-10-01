"use client";

import { useEffect, useState, type FormEvent } from "react";

import { Button, Field, inputClass } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { ACCESS_LABELS } from "@/lib/format";
import type { Approval, Device, Group } from "@/lib/types";

type AccessChoice = "" | "authorized" | "lan_only";

export function ApproveForm({ device, groups, onApproved }: { device: Device; groups: Group[]; onApproved: (result: Approval) => void }) {
  const [name, setName] = useState(device.dhcp_hostname ?? device.name);
  const [groupId, setGroupId] = useState<number | "">("");
  const [ip, setIp] = useState("");
  const [access, setAccess] = useState<AccessChoice>("");
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const group = groups.find((g) => g.id === groupId);

  useEffect(() => {
    if (groupId === "") return;
    let cancelled = false;
    api
      .get<{ ip: string | null }>(`/groups/${groupId}/next-free-ip`)
      .then((result) => {
        if (!cancelled) setIp(result.ip ?? "");
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [groupId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (groupId === "") return;
    setBusy(true);
    setError(undefined);
    try {
      const body: Record<string, unknown> = { name: name.trim(), group_id: groupId };
      if (ip.trim()) body.static_ip = ip.trim();
      if (access) body.access = access;
      onApproved(await api.post<Approval>(`/devices/${device.id}/approve`, body));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  const choices: { value: AccessChoice; label: string; hint: string }[] = [
    { value: "", label: `Group default (${group ? ACCESS_LABELS[group.default_access] : "—"})`, hint: "Use the group's policy" },
    { value: "authorized", label: "Full network", hint: "Reservation with normal DNS and gateway" },
    { value: "lan_only", label: "LAN only", hint: "No gateway: home devices yes, internet no" },
  ];

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Name">
          <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} required maxLength={64} />
        </Field>
        <Field label="Group">
          <select className={inputClass} value={groupId} onChange={(e) => setGroupId(Number(e.target.value))} required>
            <option value="" disabled>
              Choose a group…
            </option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field label="Static IP" hint={group ? `Range ${group.range_start}–${group.range_end}; leave empty for the next free address` : undefined}>
        <input className={`${inputClass} font-mono`} value={ip} onChange={(e) => setIp(e.target.value)} inputMode="decimal" />
      </Field>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-[13px] font-medium text-text2">Access</legend>
        {choices.map((choice) => (
          <label
            key={choice.value || "default"}
            className="flex cursor-pointer items-start gap-3 rounded-lg border border-line2 p-3 has-[:checked]:border-accent has-[:checked]:bg-accent-soft"
          >
            <input
              type="radio"
              name={`access-${device.id}`}
              className="mt-1 size-4 accent-[var(--accent)]"
              checked={access === choice.value}
              onChange={() => setAccess(choice.value)}
              aria-label={choice.label.startsWith("Group default") ? "Group default" : choice.label}
            />
            <span className="flex flex-col gap-0.5">
              <span className="text-sm font-semibold">{choice.label}</span>
              <span className="text-xs text-muted">{choice.hint}</span>
            </span>
          </label>
        ))}
      </fieldset>
      {error && (
        <p role="alert" className="rounded-lg border border-bad px-3 py-2 text-sm text-bad">
          {error}
        </p>
      )}
      <Button type="submit" variant="primary" disabled={busy || groupId === ""}>
        Approve and assign IP
      </Button>
    </form>
  );
}
