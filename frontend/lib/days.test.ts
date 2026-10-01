import { describe, expect, it } from "vitest";

import { describeDays, hasDay, toggleDay } from "@/lib/days";

describe("days bitmask", () => {
  it("Monday is bit zero", () => {
    expect(hasDay(0b0000001, 0)).toBe(true);
    expect(hasDay(0b0000001, 6)).toBe(false);
  });

  it("toggles days", () => {
    expect(toggleDay(127, 6)).toBe(63);
    expect(toggleDay(63, 6)).toBe(127);
  });

  it("describes masks", () => {
    expect(describeDays(127)).toBe("Every day");
    expect(describeDays(31)).toBe("Weekdays");
    expect(describeDays(96)).toBe("Weekends");
    expect(describeDays(5)).toBe("Mon, Wed");
  });
});
