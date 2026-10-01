"use client";

import { useEffect, useState, type FormEvent } from "react";

import { RulesTable } from "@/app/(app)/notifications/rules-table";
import { Button, Card, Field, Notice, PageHeader, SectionTitle, inputClass } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import type { NotifySettings, Rule } from "@/lib/types";
import { useResource } from "@/lib/use-resource";

export default function NotificationsPage() {
  const res = useResource<{ settings: NotifySettings; rules: Rule[] }>("/notifications");
  const [draft, setDraft] = useState<NotifySettings>();
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string }>();
  useEffect(() => {
    if (res.data) setDraft(res.data.settings);
  }, [res.data]);

  if (res.error) return <Notice tone="error">{res.error}</Notice>;
  if (!res.data || !draft) return <p className="text-muted">Loading…</p>;
  const set = <K extends keyof NotifySettings>(key: K, value: NotifySettings[K]) => setDraft((d) => (d ? { ...d, [key]: value } : d));

  async function save(event: FormEvent) {
    event.preventDefault();
    try {
      await api.put("/notifications/settings", { ...draft, quiet_start: draft?.quiet_start || null, quiet_end: draft?.quiet_end || null });
      setNotice({ tone: "success", text: "Notification settings saved." });
      await res.reload();
    } catch (err) {
      setNotice({ tone: "error", text: errorText(err) });
    }
  }

  async function changeRule(rule: Rule) {
    try {
      await api.put("/notifications/rules", [{ event_type: rule.event_type, email: rule.email, gotify: rule.gotify }]);
      await res.reload();
    } catch (err) {
      setNotice({ tone: "error", text: errorText(err) });
    }
  }

  async function test(channel: "email" | "gotify") {
    try {
      await api.post(`/notifications/test/${channel}`);
      setNotice({ tone: "success", text: `Test sent to ${channel === "email" ? "email" : "Gotify"} — it arrives within a minute.` });
    } catch (err) {
      setNotice({ tone: "error", text: errorText(err) });
    }
  }

  return (
    <>
      <PageHeader title="Notifications" subtitle="choose channels and what reaches you" />
      {notice && <Notice tone={notice.tone}>{notice.text}</Notice>}
      <form onSubmit={save} className="flex flex-col gap-5">
        <Card className="flex flex-wrap items-center justify-between gap-4 p-5">
          <label className="flex min-h-11 items-center gap-3 text-[15px] font-semibold">
            <input type="checkbox" className="size-5 accent-[var(--accent)]" checked={draft.enabled} onChange={(e) => set("enabled", e.target.checked)} />
            Notifications on
          </label>
          <Button type="submit" variant="primary">
            Save settings
          </Button>
        </Card>
        <div className="grid gap-5 lg:grid-cols-2">
          <Card className="flex flex-col gap-4 p-5">
            <label className="flex items-center justify-between gap-3">
              <span className="flex flex-col">
                <SectionTitle>Email</SectionTitle>
                <span className="text-[13px] text-muted">via Stalwart · no-reply</span>
              </span>
              <input type="checkbox" aria-label="Email enabled" className="size-5 accent-[var(--accent)]" checked={draft.email_enabled} onChange={(e) => set("email_enabled", e.target.checked)} />
            </label>
            <Field label="Recipient">
              <input className={inputClass} type="email" value={draft.email_recipient} onChange={(e) => set("email_recipient", e.target.value)} />
            </Field>
            <Button className="self-end" onClick={() => void test("email")}>
              Send test
            </Button>
          </Card>
          <Card className="flex flex-col gap-4 p-5">
            <label className="flex items-center justify-between gap-3">
              <span className="flex flex-col">
                <SectionTitle>Gotify</SectionTitle>
                <span className="text-[13px] text-muted">push to your phone</span>
              </span>
              <input type="checkbox" aria-label="Gotify enabled" className="size-5 accent-[var(--accent)]" checked={draft.gotify_enabled} onChange={(e) => set("gotify_enabled", e.target.checked)} />
            </label>
            <p className="text-sm text-muted">Priority follows the event: new devices, IP conflicts and outages are high.</p>
            <Button className="mt-auto self-end" onClick={() => void test("gotify")}>
              Send test
            </Button>
          </Card>
        </div>
        <Card className="flex flex-wrap items-end justify-between gap-4 p-5">
          <span className="flex flex-col gap-1">
            <span className="text-[15px] font-semibold">Quiet hours</span>
            <span className="text-[13px] text-muted">Silence everything except new devices; muted alerts are delivered afterwards if still true.</span>
          </span>
          <span className="flex items-center gap-3">
            <input aria-label="Quiet from" type="time" className={`${inputClass} w-32 font-mono`} value={draft.quiet_start ?? ""} onChange={(e) => set("quiet_start", e.target.value || null)} />
            <span className="text-faint">→</span>
            <input aria-label="Quiet until" type="time" className={`${inputClass} w-32 font-mono`} value={draft.quiet_end ?? ""} onChange={(e) => set("quiet_end", e.target.value || null)} />
          </span>
        </Card>
      </form>
      <Card className="mt-5 p-5">
        <SectionTitle>Events</SectionTitle>
        <div className="mt-3">
          <RulesTable rules={res.data.rules} onChange={(rule) => void changeRule(rule)} />
        </div>
      </Card>
    </>
  );
}
