import { describe, expect, it } from "vitest";

import { buildCells, rangeUsage } from "@/lib/ipplan";
import { makeDevice, makeGroup } from "@/lib/test-data";

const people = makeGroup({ id: 1, range_start: "192.168.1.10", range_end: "192.168.1.19" });
const devices = [makeDevice({ static_ip: "192.168.1.12" }), makeDevice({ static_ip: null, last_ip: "192.168.1.15" })];

describe("buildCells", () => {
  it("maps 256 addresses to groups, devices and reserved slots", () => {
    const cells = buildCells([people], devices, "192.168.1.1");
    expect(cells).toHaveLength(256);
    expect(cells[12].device?.static_ip).toBe("192.168.1.12");
    expect(cells[12].group?.id).toBe(1);
    expect(cells[15].device).toBeNull();
    expect(cells[20].group).toBeNull();
    expect([cells[0].reserved, cells[1].reserved, cells[255].reserved, cells[2].reserved]).toEqual([true, true, true, false]);
  });
});

describe("rangeUsage", () => {
  it("counts static reservations inside the range", () => {
    expect(rangeUsage(people, devices)).toEqual({ used: 1, total: 10 });
  });
});
