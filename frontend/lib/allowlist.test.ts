import { describe, expect, it } from "vitest";

import { isAllowed } from "@/lib/allowlist";

describe("isAllowed", () => {
  it("lets everyone in when the allowlist is empty", () => {
    expect(isAllowed("someone@example.org", "")).toBe(true);
    expect(isAllowed(undefined, " , ")).toBe(true);
  });

  it("matches emails case-insensitively", () => {
    expect(isAllowed("Owner@Example.org", "owner@example.org, other@example.org")).toBe(true);
    expect(isAllowed("stranger@example.org", "owner@example.org")).toBe(false);
    expect(isAllowed(null, "owner@example.org")).toBe(false);
  });
});
