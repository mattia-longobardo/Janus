import type { Device, Group } from "@/lib/types";

export function makeDevice(overrides: Partial<Device> = {}): Device {
  return {
    id: overrides.id ?? Math.random().toString(36).slice(2),
    mac: "00:00:5E:00:53:10",
    name: "LAPTOP_A",
    hostname: "laptop-a",
    group_id: 1,
    static_ip: "192.168.1.10",
    access: "authorized",
    vendor: null,
    private_mac: false,
    online: true,
    last_ip: "192.168.1.10",
    dhcp_hostname: null,
    first_seen: null,
    last_seen: null,
    last_scan_at: null,
    issues: [],
    health: "ok",
    ...overrides,
  };
}

export function makeGroup(overrides: Partial<Group> = {}): Group {
  return {
    id: 1,
    name: "People",
    color: "#6FB7FF",
    icon: "device",
    range_start: "192.168.1.10",
    range_end: "192.168.1.19",
    default_access: "authorized",
    offline_alert_hours: null,
    device_count: 0,
    scan_enabled: false,
    scan_interval_hours: 168,
    ...overrides,
  };
}
