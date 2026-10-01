"use client";

import clsx from "clsx";
import { Plus } from "lucide-react";
import { useMemo, useState } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button, Card, Field, Notice, PageHeader, SectionTitle, inputClass } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { DAY_NAMES, describeDays, hasDay, toggleDay } from "@/lib/days";
import { useSettings } from "@/lib/settings-context";
import type { MaintenanceWindow } from "@/lib/types";
import { useResource } from "@/lib/use-resource";

export default function SettingsPage() {
  const { settings, reload } = useSettings();
  const windowsRes = useResource<MaintenanceWindow[]>("/maintenance-windows");
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string }>();
  const zones = useMemo(() => (typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : [settings.timezone]), [settings.timezone]);

  async function saveGeneral(patch: { timezone?: string; time_format?: "24h" | "12h" }) {
    try {
      await api.put("/settings", patch);
      await reload();
      setNotice({ tone: "success", text: "Saved." });
    } catch (err) {
      setNotice({ tone: "error", text: errorText(err) });
    }
  }

  async function addWindow() {
    try {
      await api.post("/maintenance-windows", { name: "New window", start_time: "03:00", duration_min: 15, days: 127 });
      await windowsRes.reload();
    } catch (err) {
      setNotice({ tone: "error", text: errorText(err) });
    }
  }

  return (
    <>
      <PageHeader title="Settings" subtitle="general · maintenance · network · access control" />
      {notice && <Notice tone={notice.tone}>{notice.text}</Notice>}
      <div className="grid items-start gap-5 xl:grid-cols-2">
        <div className="flex flex-col gap-5">
          <Card className="flex flex-col gap-4 p-5">
            <SectionTitle>General</SectionTitle>
            <Field label="Timezone" hint="Used for schedules, quiet hours, maintenance windows and every timestamp.">
              <select className={inputClass} value={settings.timezone} onChange={(e) => void saveGeneral({ timezone: e.target.value })}>
                {zones.map((zone) => (
                  <option key={zone} value={zone}>
                    {zone}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Time format">
              <select className={inputClass} value={settings.time_format} onChange={(e) => void saveGeneral({ time_format: e.target.value as "24h" | "12h" })}>
                <option value="24h">24-hour</option>
                <option value="12h">12-hour</option>
              </select>
            </Field>
            <div className="flex flex-col gap-2">
              <span className="text-[13px] font-medium text-text2">Theme</span>
              <ThemeToggle />
            </div>
          </Card>
          <Card className="flex flex-col gap-4 p-5">
            <div className="flex items-center justify-between">
              <SectionTitle>Maintenance windows</SectionTitle>
              <Button onClick={() => void addWindow()}>
                <Plus className="size-4" aria-hidden />
                Add
              </Button>
            </div>
            {(windowsRes.data ?? []).map((w) => (
              <WindowEditor key={w.id} window={w} onChanged={() => void windowsRes.reload()} onError={(text) => setNotice({ tone: "error", text })} />
            ))}
          </Card>
        </div>
        <div className="flex flex-col gap-5">
          <Card className="p-5">
            <SectionTitle>Network</SectionTitle>
            <dl className="mt-3 grid grid-cols-[150px_1fr] gap-x-3 gap-y-2.5 text-sm">
              <dt className="text-faint">Subnet</dt>
              <dd className="font-mono">{settings.network.subnet}</dd>
              <dt className="text-faint">Gateway</dt>
              <dd className="font-mono">{settings.network.gateway}</dd>
              <dt className="text-faint">Interface</dt>
              <dd className="font-mono">{settings.network.sentinel_interface}</dd>
              <dt className="text-faint">Pi-hole</dt>
              <dd className="break-all font-mono">{settings.network.pihole_url}</dd>
              <dt className="text-faint">ARP sweep</dt>
              <dd className="font-mono">every {settings.network.sweep_interval_s} s</dd>
              <dt className="text-faint">Scan window</dt>
              <dd className="font-mono">
                {settings.scan_window.start}–{settings.scan_window.end}
              </dd>
            </dl>
          </Card>
          <Card className="p-5">
            <SectionTitle>Access control</SectionTitle>
            <dl className="mt-3 grid grid-cols-[150px_1fr] gap-x-3 gap-y-2.5 text-sm">
              <dt className="text-faint">Pi-hole sync</dt>
              <dd>
                <span className={clsx("font-mono", settings.sync_mode === "apply" ? "text-ok" : "text-accent-text")}>{settings.sync_mode}</span>
                <span className="block text-xs text-faint">
                  {settings.sync_mode === "apply" ? "Reservations and quarantine are enforced." : "Janus only compares; nothing is written to Pi-hole yet."}
                </span>
              </dd>
              <dt className="text-faint">Quarantine pool</dt>
              <dd className="font-mono">
                {settings.network.quarantine_start}–{settings.network.quarantine_end.split(".")[3]}
              </dd>
            </dl>
          </Card>
        </div>
      </div>
    </>
  );
}

function WindowEditor({ window: w, onChanged, onError }: { window: MaintenanceWindow; onChanged: () => void; onError: (text: string) => void }) {
  const [draft, setDraft] = useState(w);
  const dirty = JSON.stringify(draft) !== JSON.stringify(w);
  const set = <K extends keyof MaintenanceWindow>(key: K, value: MaintenanceWindow[K]) => setDraft((d) => ({ ...d, [key]: value }));

  async function save() {
    try {
      const { id: _id, ...body } = draft;
      await api.patch(`/maintenance-windows/${w.id}`, body);
      onChanged();
    } catch (err) {
      onError(errorText(err));
    }
  }

  async function remove() {
    if (!globalThis.confirm(`Delete ${w.name}?`)) return;
    try {
      await api.del(`/maintenance-windows/${w.id}`);
      onChanged();
    } catch (err) {
      onError(errorText(err));
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-line p-4">
      <div className="flex items-center justify-between gap-3">
        <input aria-label="Window name" className={`${inputClass} font-semibold`} value={draft.name} onChange={(e) => set("name", e.target.value)} />
        <label className="flex shrink-0 items-center gap-2 text-sm text-text2">
          <input type="checkbox" className="size-5 accent-[var(--accent)]" checked={draft.enabled} onChange={(e) => set("enabled", e.target.checked)} />
          On
        </label>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Start">
          <input type="time" className={`${inputClass} font-mono`} value={draft.start_time} onChange={(e) => set("start_time", e.target.value)} />
        </Field>
        <Field label="Minutes">
          <input type="number" min={1} max={720} className={`${inputClass} font-mono`} value={draft.duration_min} onChange={(e) => set("duration_min", Number(e.target.value))} />
        </Field>
      </div>
      <fieldset>
        <legend className="mb-2 text-[13px] font-medium text-text2">Days · {describeDays(draft.days)}</legend>
        <div className="flex flex-wrap gap-1.5">
          {DAY_NAMES.map((day, index) => (
            <button
              key={day}
              type="button"
              aria-pressed={hasDay(draft.days, index)}
              onClick={() => set("days", toggleDay(draft.days, index) || draft.days)}
              className={clsx(
                "h-9 w-12 rounded-md border text-xs font-medium",
                hasDay(draft.days, index) ? "border-accent bg-accent-soft text-text" : "border-line2 text-muted",
              )}
            >
              {day}
            </button>
          ))}
        </div>
      </fieldset>
      <label className="flex items-center gap-2 text-sm text-text2">
        <input type="checkbox" className="size-5 accent-[var(--accent)]" checked={draft.mute_alerts} onChange={(e) => set("mute_alerts", e.target.checked)} />
        Mute offline and infrastructure alerts (new devices still alert)
      </label>
      <div className="flex justify-between gap-3">
        <Button variant="danger" onClick={() => void remove()}>
          Delete
        </Button>
        <Button variant="primary" disabled={!dirty} onClick={() => void save()}>
          Save
        </Button>
      </div>
    </div>
  );
}
