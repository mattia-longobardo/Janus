"use client";

import clsx from "clsx";
import { Bell, Clock3, Grid2x2, House, Layers, LogOut, Monitor, NotepadText, Settings, Share2, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { logout } from "@/lib/auth-actions";
import { describeDays } from "@/lib/days";
import { relativeTime } from "@/lib/format";
import { useSettings } from "@/lib/settings-context";
import type { Device, MaintenanceWindow } from "@/lib/types";
import { useResource } from "@/lib/use-resource";

const NAV = [
  { href: "/", label: "Overview", icon: House },
  { href: "/map", label: "Network map", icon: Share2 },
  { href: "/devices", label: "Devices", icon: Monitor, count: "all" },
  { href: "/pending", label: "Pending", icon: Clock3, count: "pending" },
  { href: "/ip-plan", label: "IP plan", icon: Grid2x2 },
  { href: "/groups", label: "Groups", icon: Layers },
  { href: "/notifications", label: "Notifications", icon: Bell },
  { href: "/events", label: "Event log", icon: NotepadText },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

export function Logo() {
  return (
    <span className="flex items-center gap-2.5">
      <svg width="28" height="28" viewBox="0 0 32 32" fill="none" stroke="var(--accent)" strokeWidth="2.2" strokeLinecap="round" aria-hidden>
        <path d="M13 4a12 12 0 0 0 0 24" />
        <path d="M19 4a12 12 0 0 1 0 24" />
        <path d="M16 9v14" />
      </svg>
      <span className="font-display text-2xl font-bold tracking-tight">Janus</span>
    </span>
  );
}

export function Sidebar({ open, onClose, user }: { open: boolean; onClose: () => void; user: string }) {
  const pathname = usePathname();
  const { settings } = useSettings();
  const { data: devices } = useResource<Device[]>("/devices", { refreshMs: 30_000 });
  const { data: windows } = useResource<MaintenanceWindow[]>("/maintenance-windows");
  const maint = windows?.find((w) => w.enabled);
  const { status } = settings;
  const pihole = status.pihole_down_since
    ? { tone: "bg-bad", text: "Pi-hole unreachable" }
    : settings.sync_mode === "apply"
      ? { tone: "bg-ok", text: "Pi-hole DHCP · active" }
      : { tone: "bg-accent", text: "Pi-hole · dry-run" };
  const counts = {
    all: devices?.filter((d) => d.access !== "pending").length ?? 0,
    pending: devices?.filter((d) => d.access === "pending").length ?? 0,
  };
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <>
      {open && <button type="button" aria-label="Close menu" className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={onClose} />}
      <nav
        aria-label="Main"
        className={clsx(
          "fixed inset-y-0 left-0 z-40 flex w-[248px] flex-col gap-[26px] overflow-y-auto border-r border-line bg-side px-4 py-7 transition-transform lg:sticky lg:top-0 lg:h-dvh lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center justify-between px-2">
          <Logo />
          <button type="button" aria-label="Close menu" className="flex size-11 items-center justify-center lg:hidden" onClick={onClose}>
            <X className="size-5" />
          </button>
        </div>
        <ul className="flex flex-col gap-[3px]">
          {NAV.map((item) => {
            const Icon = item.icon;
            const count = "count" in item ? counts[item.count] : undefined;
            const active = isActive(item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  onClick={onClose}
                  aria-current={active ? "page" : undefined}
                  className={clsx(
                    "flex min-h-[42px] items-center gap-3 rounded-lg border px-3 text-[15px]",
                    active ? "border-line bg-card2 text-text" : "border-transparent text-muted hover:text-text",
                  )}
                >
                  <Icon className="size-[18px]" aria-hidden />
                  {item.label}
                  {count !== undefined && count > 0 && (
                    <span
                      className={clsx(
                        "ml-auto rounded-full px-2 py-0.5 font-mono text-xs",
                        "count" in item && item.count === "pending" ? "bg-accent text-accent-ink" : "bg-line text-text2",
                      )}
                    >
                      {count}
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
        <div className="mt-auto flex flex-col gap-2.5 rounded-[10px] border border-line p-3.5 text-[13px] text-muted">
          <span className="flex items-center gap-2">
            <span className={clsx("size-2 rounded-full", pihole.tone)} />
            {pihole.text}
          </span>
          <span className="flex items-center gap-2">
            <span className={clsx("size-2 rounded-full", status.sentinel_down_since ? "bg-bad" : "bg-ok")} />
            ARP scanner · {settings.network.sentinel_interface || "—"}
          </span>
          {maint && (
            <span className="flex items-center gap-2">
              <span className={clsx("size-2 rounded-full", status.maintenance_active ? "bg-accent" : "bg-faint")} />
              Maintenance {describeDays(maint.days) === "Every day" ? "daily" : describeDays(maint.days).toLowerCase()} {maint.start_time}
            </span>
          )}
          <span className="font-mono text-xs text-faint">
            last scan {relativeTime(status.last_sweep_at)} · {settings.timezone}
          </span>
          <form action={logout} className="flex items-center justify-between gap-2 border-t border-line pt-2.5">
            <span className="truncate text-xs">{user}</span>
            <button type="submit" aria-label="Sign out" title="Sign out" className="flex size-8 items-center justify-center text-muted hover:text-text">
              <LogOut className="size-4" />
            </button>
          </form>
        </div>
      </nav>
    </>
  );
}
