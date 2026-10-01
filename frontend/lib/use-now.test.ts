import { describe, expect, it } from "vitest";

import { nextScanIn } from "@/lib/use-now";

describe("nextScanIn", () => {
  const last = "2026-10-01T10:00:00Z";
  const at = (s: number) => Date.parse(last) + s * 1000;
  it("counts down to the next sweep", () => {
    expect(nextScanIn(last, 60, at(12))).toBe("next in 48 s");
    expect(nextScanIn(last, 600, at(0))).toBe("next in 10 min");
  });
  it("says scanning once the sweep is due and handles missing data", () => {
    expect(nextScanIn(last, 60, at(61))).toBe("scanning…");
    expect(nextScanIn(null, 60, at(0))).toBeNull();
  });
});
