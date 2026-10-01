import { describe, expect, it } from "vitest";

import { adviceList, riskLevel, sortServices } from "@/components/device-security";
import { makeDevice } from "@/lib/test-data";
import type { ServiceItem } from "@/lib/types";

const svc = (port: number, service: string | null, risk: ServiceItem["risk"]): ServiceItem => ({
  port, proto: "tcp", state: "open", service, version: null, risk, risk_reason: null,
  first_seen: "2026-10-01T10:00:00Z", last_seen: "2026-10-01T10:00:00Z",
});
const window = { start: "08:00", end: "22:00" };

describe("riskLevel", () => {
  it("takes the worst service", () => {
    expect(riskLevel([])).toBe("None");
    expect(riskLevel([svc(80, "http", "none")])).toBe("Low");
    expect(riskLevel([svc(80, "http", "none"), svc(1900, "upnp", "warning")])).toBe("Medium");
    expect(riskLevel([svc(1900, "upnp", "warning"), svc(23, "telnet", "high")])).toBe("High");
  });

  it("sorts risky services first", () => {
    expect(sortServices([svc(80, "http", "none"), svc(1900, "upnp", "warning"), svc(23, "telnet", "high")]).map((s) => s.port)).toEqual([23, 1900, 80]);
  });
});

describe("adviceList", () => {
  it("gives one tip per risky service", () => {
    const device = makeDevice({ last_scan_at: "2026-10-01T10:00:00Z" });
    const tips = adviceList(device, [svc(23, "telnet", "high"), svc(21, "ftp", "high"), svc(80, "http", "none")], window);
    expect(tips).toHaveLength(2);
    expect(tips[0]).toMatch(/FTP/);
    expect(tips[1]).toMatch(/telnet/);
  });

  it("explains unscanned, clean and LAN-only devices", () => {
    expect(adviceList(makeDevice({ last_scan_at: null }), [], window)[0]).toMatch(/Not scanned yet.*08:00 and 22:00/);
    expect(adviceList(makeDevice({ last_scan_at: "2026-10-01T10:00:00Z" }), [], window)).toEqual(["No open ports found. Nothing to do."]);
    expect(adviceList(makeDevice({ last_scan_at: "2026-10-01T10:00:00Z", access: "lan_only" }), [svc(80, "http", "none")], window)).toEqual([
      "No risky services found. Rescan after firmware updates.",
      "LAN only is active: the device reaches home devices but never the internet.",
    ]);
  });
});
