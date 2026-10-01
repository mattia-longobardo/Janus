import { describe, expect, it } from "vitest";

import { deviceIp, formatDateTime, ipSortKey, relativeTime } from "@/lib/format";

describe("formatDateTime", () => {
  it("formats in the configured zone, 24 h by default", () => {
    expect(formatDateTime("2026-10-01T03:00:00Z", "Europe/Rome")).toBe("01/10 05:00");
    expect(formatDateTime("2026-10-01T03:00:00Z", "UTC")).toBe("01/10 03:00");
  });

  it("supports 12 h and missing values", () => {
    expect(formatDateTime("2026-10-01T15:30:00Z", "UTC", "12h")).toBe("01/10 03:30 PM");
    expect(formatDateTime(null, "UTC")).toBe("—");
  });
});

describe("relativeTime", () => {
  const now = Date.parse("2026-10-01T12:00:00Z");
  it.each([
    ["2026-10-01T11:59:30Z", "now"],
    ["2026-10-01T11:45:00Z", "15 min ago"],
    ["2026-10-01T09:00:00Z", "3 h ago"],
    ["2026-09-28T12:00:00Z", "3 d ago"],
  ])("%s → %s", (iso, expected) => {
    expect(relativeTime(iso, now)).toBe(expected);
  });

  it("handles never-seen devices", () => {
    expect(relativeTime(null, now)).toBe("never");
  });
});

describe("ip helpers", () => {
  it("sorts numerically and prefers the static IP", () => {
    expect(["192.168.1.20", "192.168.1.3", "192.168.1.100"].sort((a, b) => ipSortKey(a) - ipSortKey(b))).toEqual([
      "192.168.1.3", "192.168.1.20", "192.168.1.100",
    ]);
    expect(ipSortKey(null)).toBe(Number.MAX_SAFE_INTEGER);
    expect(deviceIp({ static_ip: "192.168.1.10", last_ip: "192.168.1.170" })).toBe("192.168.1.10");
    expect(deviceIp({ static_ip: null, last_ip: "192.168.1.170" })).toBe("192.168.1.170");
  });
});
