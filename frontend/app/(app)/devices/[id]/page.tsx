"use client";

import clsx from "clsx";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { EventList } from "@/components/event-list";
import { Badge, Button, Card, Field, Notice, SectionTitle, StatusDot, inputClass } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { ACCESS_LABELS, deviceIp, formatDateTime, relativeTime } from "@/lib/format";
import { useSettings } from "@/lib/settings-context";
import type { Access, Approval, Device, DnsActivity, EventItem, Facts, Group, ServiceItem } from "@/lib/types";
import { useResource } from "@/lib/use-resource";

const TABS = ["identity", "security", "activity"] as const;
type Tab = (typeof TABS)[number];
const FIELD_LABELS: Record<string, string> = {
  vendor: "Vendor", type: "Device type", os: "Operating system", hostname: "Hostname", model: "Model",
  services: "Announced services", ssdp_server: "UPnP server",
};
const SOURCE_LABELS: Record<string, string> = { oui: "IEEE OUI", dhcp: "DHCP", mdns: "mDNS", netbios: "NetBIOS", ssdp: "SSDP" };

export default function DevicePage() {
  const { id } = useParams<{ id: string }>();
  const { settings } = useSettings();
  const deviceRes = useResource<Device>(`/devices/${id}`, { refreshMs: 30_000 });
  const groupsRes = useResource<Group[]>("/groups");
  const [tab, setTab] = useState<Tab>("identity");
  const [editing, setEditing] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string }>();
  const device = deviceRes.data;
  const groups = groupsRes.data ?? [];

  if (deviceRes.error) return <Notice tone="error">{deviceRes.error}</Notice>;
  if (!device) return <p className="text-muted">Loading…</p>;
  const group = groups.find((g) => g.id === device.group_id);

  async function scan() {
    try {
      await api.post(`/devices/${id}/scan`);
      setNotice({ tone: "success", text: "Scan queued — results appear in Security within a few minutes." });
    } catch (err) {
      setNotice({ tone: "error", text: errorText(err) });
    }
  }

  async function block() {
    if (!device || !window.confirm(`Block ${device.name}?`)) return;
    try {
      const result = await api.post<Approval>(`/devices/${id}/block`);
      setNotice({ tone: "success", text: `Blocked — ${result.enforcement}` });
      await deviceRes.reload();
    } catch (err) {
      setNotice({ tone: "error", text: errorText(err) });
    }
  }

  return (
    <>
      <Link href="/devices" className="text-sm text-muted underline">
        ← All devices
      </Link>
      <header className="mb-6 mt-4 flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-2">
          <h1 className="font-display text-3xl font-bold tracking-tight lg:text-4xl">{device.name}</h1>
          <div className="flex flex-wrap items-center gap-3 text-[13px] text-muted">
            <span className="flex items-center gap-1.5">
              <StatusDot online={device.online} />
              {device.online ? "Online" : `Seen ${relativeTime(device.last_seen)}`}
            </span>
            <span className="font-mono">{deviceIp(device) ?? "no IP"}</span>
            <span className="font-mono">{device.mac ?? "no MAC"}</span>
            <Badge tone={device.access === "blocked" ? "bad" : device.access === "pending" ? "accent" : "neutral"}>
              {group?.name ?? "No group"} · {ACCESS_LABELS[device.access]}
            </Badge>
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          {device.access === "pending" ? (
            <Link href={`/pending#${device.id}`} className="inline-flex h-11 items-center rounded-lg border border-accent bg-accent px-4 text-sm font-semibold text-accent-ink">
              Approve…
            </Link>
          ) : (
            <Button onClick={() => setEditing((v) => !v)}>{editing ? "Close editor" : "Edit"}</Button>
          )}
          <Button onClick={() => void scan()} disabled={!device.last_ip}>
            Scan now
          </Button>
          {device.access !== "blocked" && (
            <Button variant="danger" onClick={() => void block()}>
              Block
            </Button>
          )}
        </div>
      </header>
      {notice && <Notice tone={notice.tone}>{notice.text}</Notice>}
      {editing && (
        <EditDevice
          device={device}
          groups={groups}
          onSaved={async () => {
            setEditing(false);
            setNotice({ tone: "success", text: "Saved." });
            await deviceRes.reload();
          }}
        />
      )}

      <div role="tablist" aria-label="Device sections" className="mb-6 flex gap-1 border-b border-line">
        {TABS.map((name) => (
          <button
            key={name}
            role="tab"
            type="button"
            aria-selected={tab === name}
            onClick={() => setTab(name)}
            className={clsx(
              "-mb-px h-11 border-b-2 px-4 text-[15px] font-semibold capitalize",
              tab === name ? "border-accent text-text" : "border-transparent text-muted",
            )}
          >
            {name}
          </button>
        ))}
      </div>
      {tab === "identity" && <IdentityTab device={device} groupName={group?.name} />}
      {tab === "security" && <SecurityTab device={device} group={group} onScan={() => void scan()} />}
      {tab === "activity" && <ActivityTab device={device} />}
      <p className="mt-8 font-mono text-xs text-faint">
        First seen {formatDateTime(device.first_seen, settings.timezone, settings.time_format)} · last seen{" "}
        {formatDateTime(device.last_seen, settings.timezone, settings.time_format)}
      </p>
    </>
  );
}

function EditDevice({ device, groups, onSaved }: { device: Device; groups: Group[]; onSaved: () => Promise<void> }) {
  const [name, setName] = useState(device.name);
  const [groupId, setGroupId] = useState<number | "">(device.group_id ?? "");
  const [ip, setIp] = useState(device.static_ip ?? "");
  const [access, setAccess] = useState<Access>(device.access);
  const [error, setError] = useState<string>();

  async function save(event: FormEvent) {
    event.preventDefault();
    setError(undefined);
    const body: Record<string, unknown> = {};
    if (name !== device.name) body.name = name;
    if (groupId !== "" && groupId !== device.group_id) body.group_id = groupId;
    if ((ip || null) !== device.static_ip) body.static_ip = ip || null;
    if (access !== device.access) body.access = access;
    try {
      await api.patch(`/devices/${device.id}`, body);
      await onSaved();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <Card className="mb-6 p-5">
      <form onSubmit={save} className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Field label="Name">
          <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} maxLength={64} required />
        </Field>
        <Field label="Group">
          <select className={inputClass} value={groupId} onChange={(e) => setGroupId(Number(e.target.value))}>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Static IP">
          <input className={`${inputClass} font-mono`} value={ip} onChange={(e) => setIp(e.target.value)} />
        </Field>
        <Field label="Access">
          <select className={inputClass} value={access} onChange={(e) => setAccess(e.target.value as Access)}>
            {(["authorized", "lan_only", "blocked"] as Access[]).map((value) => (
              <option key={value} value={value}>
                {ACCESS_LABELS[value]}
              </option>
            ))}
          </select>
        </Field>
        {error && (
          <p role="alert" className="text-sm text-bad md:col-span-2 xl:col-span-4">
            {error}
          </p>
        )}
        <div className="md:col-span-2 xl:col-span-4">
          <Button type="submit" variant="primary">
            Save changes
          </Button>
        </div>
      </form>
    </Card>
  );
}

function IdentityTab({ device, groupName }: { device: Device; groupName?: string }) {
  const { settings } = useSettings();
  const factsRes = useResource<Facts>(`/devices/${device.id}/facts`);
  const summary = factsRes.data?.summary ?? {};
  const fields = Object.keys(FIELD_LABELS).filter((field) => summary[field]);
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card className="p-5">
        <SectionTitle>Identity</SectionTitle>
        {fields.length === 0 ? (
          <p className="mt-3 text-sm text-muted">Nothing announced yet. Facts appear as the device talks on the network.</p>
        ) : (
          <dl className="mt-3">
            {fields.map((field) => (
              <div key={field} className="grid grid-cols-[140px_1fr_auto] items-center gap-3 border-b border-row py-2.5 last:border-0">
                <dt className="text-[13px] text-faint">{FIELD_LABELS[field]}</dt>
                <dd className="break-words text-sm">{summary[field].value}</dd>
                <dd>
                  <Badge>
                    {SOURCE_LABELS[summary[field].source] ?? summary[field].source} {summary[field].confidence}%
                  </Badge>
                </dd>
              </div>
            ))}
          </dl>
        )}
        <p className="mt-3 text-xs text-faint">Each value shows where it came from. Nothing is looked up outside your network.</p>
      </Card>
      <Card className="p-5">
        <SectionTitle>Network</SectionTitle>
        <dl className="mt-3 grid grid-cols-[140px_1fr] gap-x-3 gap-y-2.5 text-sm">
          <dt className="text-faint">Static IP</dt>
          <dd className="font-mono">{device.static_ip ?? "—"}</dd>
          <dt className="text-faint">Current IP</dt>
          <dd className="font-mono">{device.last_ip ?? "—"}</dd>
          <dt className="text-faint">MAC</dt>
          <dd className="font-mono">{device.mac ?? "—"}{device.private_mac ? " (private)" : ""}</dd>
          <dt className="text-faint">DHCP name</dt>
          <dd className="font-mono">{device.dhcp_hostname ?? "—"}</dd>
          <dt className="text-faint">DNS name</dt>
          <dd className="font-mono">{device.hostname}</dd>
          <dt className="text-faint">Group</dt>
          <dd>{groupName ?? "—"}</dd>
          <dt className="text-faint">Access</dt>
          <dd>{ACCESS_LABELS[device.access]}</dd>
          <dt className="text-faint">Last scan</dt>
          <dd className="font-mono">{formatDateTime(device.last_scan_at, settings.timezone, settings.time_format)}</dd>
        </dl>
      </Card>
    </div>
  );
}

function SecurityTab({ device, group, onScan }: { device: Device; group?: Group; onScan: () => void }) {
  const { settings } = useSettings();
  const servicesRes = useResource<ServiceItem[]>(`/devices/${device.id}/services`, { refreshMs: 30_000 });
  const services = servicesRes.data ?? [];
  const risky = services.filter((s) => s.risk !== "none");
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <Card className="p-5">
          <span className="text-[13px] text-muted">Open ports</span>
          <p className="font-display text-3xl font-bold">{services.length}</p>
        </Card>
        <Card className="p-5">
          <span className="text-[13px] text-muted">Risky services</span>
          <p className={clsx("font-display text-3xl font-bold", risky.length ? "text-bad" : "text-ok")}>{risky.length}</p>
        </Card>
        <Card className="col-span-2 p-5 lg:col-span-1">
          <span className="text-[13px] text-muted">Last scan</span>
          <p className="font-mono text-sm">{formatDateTime(device.last_scan_at, settings.timezone, settings.time_format)}</p>
          <p className="mt-1 text-xs text-faint">
            {group?.scan_enabled ? `Scheduled every ${group.scan_interval_hours} h` : "Scheduled scans are off for this group"}
          </p>
        </Card>
      </div>
      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <SectionTitle>Open ports</SectionTitle>
          <Button onClick={onScan} disabled={!device.last_ip}>
            Scan now
          </Button>
        </div>
        {services.length === 0 ? (
          <p className="mt-3 text-sm text-muted">{device.last_scan_at ? "No open ports found." : "Not scanned yet."}</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[620px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wider text-faint">
                  <th className="py-2 font-medium">Port</th>
                  <th className="py-2 font-medium">Service</th>
                  <th className="py-2 font-medium">Version</th>
                  <th className="py-2 font-medium">Risk</th>
                </tr>
              </thead>
              <tbody>
                {services.map((s) => (
                  <tr key={`${s.port}/${s.proto}`} className="border-b border-row">
                    <td className="py-2.5 font-mono">
                      {s.port}/{s.proto}
                    </td>
                    <td className="py-2.5">{s.service ?? "unknown"}</td>
                    <td className="py-2.5 text-muted">{s.version ?? "—"}</td>
                    <td className="py-2.5">
                      {s.risk === "none" ? (
                        <span className="text-muted">—</span>
                      ) : (
                        <span className={s.risk === "high" ? "text-bad" : "text-accent-text"} title={s.risk_reason ?? undefined}>
                          {s.risk}: {s.risk_reason}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function ActivityTab({ device }: { device: Device }) {
  const [hours, setHours] = useState(24);
  const dnsRes = useResource<DnsActivity>(device.last_ip ? `/devices/${device.id}/dns?hours=${hours}` : null);
  const eventsRes = useResource<EventItem[]>(device.mac ? `/events?mac=${encodeURIComponent(device.mac)}&limit=30` : null);
  const dns = dnsRes.data;
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <SectionTitle>DNS activity</SectionTitle>
          <select aria-label="Period" className={`${inputClass} w-36`} value={hours} onChange={(e) => setHours(Number(e.target.value))}>
            <option value={24}>Last 24 h</option>
            <option value={72}>Last 3 days</option>
            <option value={168}>Last 7 days</option>
          </select>
        </div>
        {dnsRes.error && <p className="mt-3 text-sm text-bad">{dnsRes.error}</p>}
        {!device.last_ip && <p className="mt-3 text-sm text-muted">No IP address known yet.</p>}
        {dns && (
          <>
            <p className="mt-3 font-mono text-xs text-faint">
              {dns.total} queries · {dns.blocked} blocked{dns.truncated ? ` · top domains from the latest ${dns.sampled}` : ""}
            </p>
            <ul className="mt-2">
              {dns.domains.map((d) => (
                <li key={d.domain} className="flex items-center justify-between gap-3 border-b border-row py-2 last:border-0">
                  <span className="truncate font-mono text-[13px]">{d.domain}</span>
                  <span className="flex shrink-0 items-center gap-2 font-mono text-xs">
                    {d.blocked && <Badge tone="bad">blocked</Badge>}
                    {d.count}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>
      <Card className="p-5">
        <SectionTitle>Events</SectionTitle>
        <div className="mt-3">
          <EventList events={eventsRes.data ?? []} />
        </div>
      </Card>
    </div>
  );
}
