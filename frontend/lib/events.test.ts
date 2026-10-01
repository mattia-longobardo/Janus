import { describe, expect, it } from "vitest";

import { describeEvent } from "@/lib/events";

const event = (type: string, payload: Record<string, unknown> = {}) => ({ id: 1, ts: "2026-10-01T10:00:00Z", type, mac: null, payload });

describe("describeEvent", () => {
  it.each([
    [event("device.new", { hostname: "pixel-7", ip: "192.168.1.243" }), "New device pixel-7 on 192.168.1.243"],
    [event("device.new", {}), "New device on no IP yet"],
    [event("device.approved", { name: "TV", ip: "192.168.1.153", access: "lan_only" }), "Approved TV → 192.168.1.153 (LAN only)"],
    [event("device.ip_mismatch", { name: "CAM", ip: "192.168.1.170", expected: "192.168.1.101" }), "CAM uses 192.168.1.170, reserved 192.168.1.101"],
    [event("sync.applied", { added: ["a", "b"], removed: ["c"] }), "Pi-hole reservations: +2 −1"],
    [event("security.risky_service", { ports: [{ port: 23 }, { port: 21 }] }), "Risky services on ports 23, 21"],
    [event("infra.down", { service: "pihole" }), "Pi-hole unreachable"],
    [event("maintenance.start"), "Maintenance window started"],
    [event("something.else"), "something.else"],
  ])("%j", (input, expected) => {
    expect(describeEvent(input)).toBe(expected);
  });
});
