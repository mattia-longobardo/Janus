import { describe, expect, it } from "vitest";

import { nextRun, zoneLabel } from "@/components/settings-schedule";

describe("zoneLabel", () => {
  it("adds the current UTC offset", () => {
    expect(zoneLabel("Europe/Rome", new Date("2026-10-01T10:00:00Z"))).toBe("Europe/Rome (UTC+02:00)");
    expect(zoneLabel("Europe/Rome", new Date("2026-12-01T10:00:00Z"))).toBe("Europe/Rome (UTC+01:00)");
    expect(zoneLabel("UTC", new Date("2026-10-01T10:00:00Z"))).toBe("UTC (UTC+00:00)");
  });
});

describe("nextRun", () => {
  const thursdayMorning = new Date("2026-10-01T02:00:00Z");
  it("finds the next slot in the configured zone", () => {
    expect(nextRun(127, "05:00", "Europe/Rome", thursdayMorning)).toBe("today 05:00");
    expect(nextRun(127, "03:00", "Europe/Rome", thursdayMorning)).toBe("tomorrow 03:00");
    expect(nextRun(96, "05:00", "Europe/Rome", thursdayMorning)).toBe("Sat 05:00");
    expect(nextRun(0, "05:00", "Europe/Rome", thursdayMorning)).toBe("never");
  });
});
