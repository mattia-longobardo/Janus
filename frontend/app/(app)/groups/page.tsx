"use client";

import clsx from "clsx";
import { Activity, House, Monitor, Plus, Printer, Router, Server, Smartphone, Tv, Wifi, Zap } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Button, Card, Field, Notice, PageHeader, inputClass } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { ACCESS_LABELS } from "@/lib/format";
import { rangeUsage } from "@/lib/ipplan";
import type { Access, Device, Group } from "@/lib/types";
import { useResource } from "@/lib/use-resource";

const GROUP_ICONS = { device: Monitor, phone: Smartphone, home: House, zap: Zap, activity: Activity, tv: Tv, printer: Printer, server: Server, wifi: Wifi, router: Router };
const PALETTE = ["#6FB7FF", "#B69CF0", "#E58FB8", "#5CC8A8", "#A6D86A", "#E0A84E", "#F0765C", "#9AA3A8"];
type Draft = Omit<Group, "id" | "device_count">;
const EMPTY: Draft = {
  name: "", color: PALETTE[0], icon: "device", range_start: "", range_end: "", default_access: "authorized",
  offline_alert_hours: null, scan_enabled: false, scan_interval_hours: 168,
};

export default function GroupsPage() {
  const groupsRes = useResource<Group[]>("/groups");
  const devicesRes = useResource<Device[]>("/devices");
  const [selected, setSelected] = useState<number | "new" | null>(null);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string }>();
  const groups = groupsRes.data ?? [];
  const current = typeof selected === "number" ? groups.find((g) => g.id === selected) : undefined;

  return (
    <>
      <PageHeader
        title="Groups"
        subtitle="people and device categories · each owns an IP range and a default policy"
        actions={
          <Button variant="primary" onClick={() => setSelected("new")}>
            <Plus className="size-4" aria-hidden />
            New group
          </Button>
        }
      />
      {notice && <Notice tone={notice.tone}>{notice.text}</Notice>}
      <div className="grid gap-6 xl:grid-cols-[1.1fr_1fr]">
        <Card className="overflow-hidden">
          <ul>
            {groups.map((g) => {
              const Icon = GROUP_ICONS[g.icon as keyof typeof GROUP_ICONS] ?? Monitor;
              const usage = rangeUsage(g, devicesRes.data ?? []);
              return (
                <li key={g.id}>
                  <button
                    type="button"
                    aria-pressed={selected === g.id}
                    onClick={() => setSelected(g.id)}
                    className={clsx(
                      "grid w-full grid-cols-[36px_1fr_auto] items-center gap-3 border-b border-row px-4 py-3 text-left sm:grid-cols-[36px_1fr_120px_110px]",
                      selected === g.id && "bg-accent-soft",
                    )}
                  >
                    <span className="flex size-9 items-center justify-center rounded-lg" style={{ background: `${g.color}26`, color: g.color }}>
                      <Icon className="size-[18px]" aria-hidden />
                    </span>
                    <span className="flex flex-col">
                      <span className="font-semibold">{g.name}</span>
                      <span className="font-mono text-xs text-faint">
                        {g.range_start}–{g.range_end.split(".")[3]} · {usage.used}/{usage.total}
                      </span>
                    </span>
                    <span className="hidden text-[13px] text-muted sm:block">{ACCESS_LABELS[g.default_access]}</span>
                    <span className="text-[13px] text-muted">{g.scan_enabled ? `scan ${g.scan_interval_hours} h` : "no scan"}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </Card>
        {selected !== null && (
          <GroupEditor
            key={selected}
            group={current}
            onDone={async (text) => {
              setNotice({ tone: "success", text });
              setSelected(null);
              await groupsRes.reload();
            }}
            onError={(text) => setNotice({ tone: "error", text })}
          />
        )}
      </div>
    </>
  );
}

function GroupEditor({ group, onDone, onError }: { group?: Group; onDone: (text: string) => Promise<void>; onError: (text: string) => void }) {
  const [draft, setDraft] = useState<Draft>(group ? { ...group } : EMPTY);
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value }));

  async function save(event: FormEvent) {
    event.preventDefault();
    try {
      if (group) {
        await api.patch(`/groups/${group.id}`, draft);
        await onDone(`${draft.name} saved.`);
      } else {
        await api.post("/groups", draft);
        await onDone(`${draft.name} created.`);
      }
    } catch (err) {
      onError(errorText(err));
    }
  }

  async function remove() {
    if (!group || !window.confirm(`Delete ${group.name}?`)) return;
    try {
      await api.del(`/groups/${group.id}`);
      await onDone(`${group.name} deleted.`);
    } catch (err) {
      onError(errorText(err));
    }
  }

  return (
    <Card className="p-5 lg:p-6">
      <form onSubmit={save} className="flex flex-col gap-5">
        <h2 className="font-display text-2xl font-bold">{group ? group.name : "New group"}</h2>
        <Field label="Name">
          <input className={inputClass} value={draft.name} onChange={(e) => set("name", e.target.value)} required maxLength={64} />
        </Field>
        <fieldset>
          <legend className="mb-2 text-[13px] font-medium text-text2">Colour</legend>
          <div className="flex flex-wrap gap-2">
            {PALETTE.map((color) => (
              <button
                key={color}
                type="button"
                aria-label={`Colour ${color}`}
                aria-pressed={draft.color.toUpperCase() === color}
                onClick={() => set("color", color)}
                className={clsx("size-9 rounded-lg border", draft.color.toUpperCase() === color ? "border-[3px] border-text" : "border-line2")}
                style={{ background: color }}
              />
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend className="mb-2 text-[13px] font-medium text-text2">Icon</legend>
          <div className="flex flex-wrap gap-2">
            {Object.entries(GROUP_ICONS).map(([key, Icon]) => (
              <button
                key={key}
                type="button"
                aria-label={`Icon ${key}`}
                aria-pressed={draft.icon === key}
                onClick={() => set("icon", key)}
                className={clsx(
                  "flex size-11 items-center justify-center rounded-lg border",
                  draft.icon === key ? "border-accent bg-accent-soft" : "border-line2 bg-card",
                )}
              >
                <Icon className="size-[18px]" aria-hidden />
              </button>
            ))}
          </div>
        </fieldset>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Range start">
            <input className={`${inputClass} font-mono`} value={draft.range_start} onChange={(e) => set("range_start", e.target.value)} required />
          </Field>
          <Field label="Range end">
            <input className={`${inputClass} font-mono`} value={draft.range_end} onChange={(e) => set("range_end", e.target.value)} required />
          </Field>
        </div>
        <Field label="Default access for new members" hint="LAN only: no gateway, so the device reaches home devices but never the internet.">
          <select className={inputClass} value={draft.default_access} onChange={(e) => set("default_access", e.target.value as Access)}>
            <option value="authorized">{ACCESS_LABELS.authorized}</option>
            <option value="lan_only">{ACCESS_LABELS.lan_only}</option>
          </select>
        </Field>
        <Field label="Offline alert after (hours)" hint="Leave empty for no offline alerts.">
          <input
            className={`${inputClass} font-mono`}
            type="number"
            min={1}
            value={draft.offline_alert_hours ?? ""}
            onChange={(e) => set("offline_alert_hours", e.target.value ? Number(e.target.value) : null)}
          />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="flex min-h-11 items-center gap-3 text-sm text-text2">
            <input type="checkbox" className="size-5 accent-[var(--accent)]" checked={draft.scan_enabled} onChange={(e) => set("scan_enabled", e.target.checked)} />
            Scheduled port scans
          </label>
          <Field label="Scan every (hours)">
            <input
              className={`${inputClass} font-mono`}
              type="number"
              min={1}
              max={720}
              value={draft.scan_interval_hours}
              onChange={(e) => set("scan_interval_hours", Number(e.target.value))}
            />
          </Field>
        </div>
        <div className="flex flex-wrap justify-between gap-3 border-t border-line pt-4">
          {group ? (
            <Button variant="danger" onClick={() => void remove()}>
              Delete group
            </Button>
          ) : (
            <span />
          )}
          <Button type="submit" variant="primary">
            {group ? "Save changes" : "Create group"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
