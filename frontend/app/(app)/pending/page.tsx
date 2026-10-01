"use client";

import { useState } from "react";

import { ApproveForm } from "@/components/approve-form";
import { Badge, Button, Card, Notice, PageHeader } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useSettings } from "@/lib/settings-context";
import type { Approval, Device, Group } from "@/lib/types";
import { useResource } from "@/lib/use-resource";

export default function PendingPage() {
  const { settings } = useSettings();
  const devicesRes = useResource<Device[]>("/devices?access=pending", { refreshMs: 30_000 });
  const groupsRes = useResource<Group[]>("/groups");
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string }>();
  const pending = devicesRes.data ?? [];
  const groups = groupsRes.data ?? [];

  function approved(result: Approval) {
    const enforcement = result.enforcement === "dry-run" ? "saved (Pi-hole is in dry-run)" : result.enforcement;
    setNotice({ tone: "success", text: `${result.device.name} approved on ${result.device.static_ip} — ${enforcement}` });
    void devicesRes.reload();
  }

  async function block(device: Device) {
    if (!window.confirm(`Block ${device.name}? It will get no network.`)) return;
    try {
      const result = await api.post<Approval>(`/devices/${device.id}/block`);
      setNotice({ tone: "success", text: `${result.device.name} blocked — ${result.enforcement}` });
      await devicesRes.reload();
    } catch (err) {
      setNotice({ tone: "error", text: errorText(err) });
    }
  }

  return (
    <>
      <PageHeader
        title="Pending devices"
        subtitle={settings.sync_mode === "apply" ? "in quarantine until you decide" : "detected — quarantine starts when Pi-hole serves DHCP"}
      />
      {notice && <Notice tone={notice.tone}>{notice.text}</Notice>}
      {devicesRes.error && <Notice tone="error">{devicesRes.error}</Notice>}
      {pending.length === 0 ? (
        <Card className="p-8 text-center text-muted">Nothing is waiting. New devices appear here as soon as they connect.</Card>
      ) : (
        <div className="flex flex-col gap-5">
          {pending.map((device) => (
            <Card key={device.id} id={device.id} className="grid gap-6 p-5 lg:grid-cols-[1fr_1.2fr] lg:p-6">
              <div className="flex flex-col gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-display text-2xl font-bold">{device.name}</h2>
                  {device.private_mac && <Badge tone="accent">private MAC</Badge>}
                </div>
                <dl className="grid grid-cols-[130px_1fr] gap-x-3 gap-y-2 text-sm">
                  <dt className="text-faint">MAC</dt>
                  <dd className="font-mono">{device.mac}</dd>
                  <dt className="text-faint">Vendor</dt>
                  <dd>{device.vendor ?? (device.private_mac ? "Hidden (private MAC)" : "Unknown")}</dd>
                  <dt className="text-faint">DHCP name</dt>
                  <dd className="font-mono">{device.dhcp_hostname ?? "—"}</dd>
                  <dt className="text-faint">Current IP</dt>
                  <dd className="font-mono">{device.last_ip ?? "—"}</dd>
                  <dt className="text-faint">First seen</dt>
                  <dd className="font-mono">{formatDateTime(device.first_seen, settings.timezone, settings.time_format)}</dd>
                </dl>
                <Button variant="danger" className="mt-auto self-start" onClick={() => void block(device)}>
                  Block
                </Button>
              </div>
              <ApproveForm device={device} groups={groups} onApproved={approved} />
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
