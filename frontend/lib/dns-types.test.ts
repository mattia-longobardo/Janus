import { describe, expect, it } from "vitest";

import { busiest, filterDomains, sortDomains, type DnsDomainRow } from "@/lib/dns-types";

const rows: DnsDomainRow[] = [
  { domain: "b.example.org", base: "example.org", count: 5, blocked: false, last_seen: "2026-10-01T10:00:00+02:00" },
  { domain: "ads.tracker.net", base: "tracker.net", count: 9, blocked: true, last_seen: "2026-10-01T09:00:00+02:00" },
  { domain: "a.example.org", base: "example.org", count: 1, blocked: false, last_seen: null },
];

describe("dns helpers", () => {
  it("sorts by any column", () => {
    expect(sortDomains(rows, "count", "desc").map((r) => r.count)).toEqual([9, 5, 1]);
    expect(sortDomains(rows, "domain", "asc")[0].domain).toBe("a.example.org");
    expect(sortDomains(rows, "base", "asc").map((r) => r.domain)).toEqual(["a.example.org", "b.example.org", "ads.tracker.net"]);
    expect(sortDomains(rows, "last_seen", "desc")[0].domain).toBe("b.example.org");
  });

  it("filters by text and blocked flag", () => {
    expect(filterDomains(rows, "EXAMPLE", false)).toHaveLength(2);
    expect(filterDomains(rows, "", true).map((r) => r.domain)).toEqual(["ads.tracker.net"]);
  });

  it("finds the busiest bucket", () => {
    expect(busiest([{ start: "a", total: 2, blocked: 0 }, { start: "b", total: 7, blocked: 1 }])?.start).toBe("b");
    expect(busiest([{ start: "a", total: 0, blocked: 0 }])).toBeNull();
  });
});
