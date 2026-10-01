import { describe, expect, it } from "vitest";

import { devicesCsv } from "@/components/ip-plan-export";
import { makeDevice, makeGroup } from "@/lib/test-data";

describe("devicesCsv", () => {
  it("exports approved devices and quotes awkward values", () => {
    const csv = devicesCsv(
      [
        makeDevice({ name: 'TV, "sala"', mac: "00:00:5E:00:53:10", static_ip: "192.168.1.150", group_id: 1 }),
        makeDevice({ name: "Unknown", access: "pending", group_id: null }),
      ],
      [makeGroup({ id: 1, name: "Streaming" })],
    );
    expect(csv).toBe('name,mac,static_ip,group\n"TV, ""sala""",00:00:5E:00:53:10,192.168.1.150,Streaming\n');
  });
});
