import { describe, expect, it } from "vitest";

import { NODE_H, NODE_W, autoLayout, groupBoxes, groupKey } from "@/lib/map-layout";
import { makeDevice, makeGroup } from "@/lib/test-data";

const groups = [
  makeGroup({ id: 1, range_start: "192.168.1.10", range_end: "192.168.1.19" }),
  makeGroup({ id: 2, name: "Power meters", range_start: "192.168.1.120", range_end: "192.168.1.129" }),
];
const devices = [
  ...Array.from({ length: 9 }, (_, i) => makeDevice({ id: `m${i}`, group_id: 2, static_ip: `192.168.1.${120 + i}` })),
  ...Array.from({ length: 6 }, (_, i) => makeDevice({ id: `p${i}`, group_id: 1, static_ip: `192.168.1.${10 + i}` })),
  makeDevice({ id: "gw", name: "Gateway", group_id: null, static_ip: null, last_ip: "192.168.1.1" }),
  makeDevice({ id: "q1", access: "pending", group_id: null, static_ip: null, last_ip: "192.168.1.243" }),
];

function overlaps(a: { x: number; y: number }, b: { x: number; y: number }) {
  return a.x < b.x + NODE_W && b.x < a.x + NODE_W && a.y < b.y + NODE_H && b.y < a.y + NODE_H;
}

describe("autoLayout", () => {
  const positions = autoLayout(devices, groups);

  it("places every device without overlaps", () => {
    expect(Object.keys(positions)).toHaveLength(devices.length);
    const list = Object.values(positions);
    for (let i = 0; i < list.length; i += 1) {
      for (let j = i + 1; j < list.length; j += 1) expect(overlaps(list[i], list[j])).toBe(false);
    }
  });

  it("keeps a group in one column ordered by IP", () => {
    const meters = devices.filter((d) => d.group_id === 2).map((d) => positions[d.id]);
    expect(new Set(meters.map((p) => p.x)).size).toBe(1);
    expect(meters.map((p) => p.y)).toEqual([...meters.map((p) => p.y)].sort((a, b) => a - b));
  });

  it("puts each device inside its own group box and boxes never overlap", () => {
    const boxes = groupBoxes(devices, positions);
    expect(boxes.map((b) => b.key).sort()).toEqual(["g1", "g2", "pending", "ungrouped"]);
    for (const device of devices) {
      const box = boxes.find((b) => b.key === groupKey(device))!;
      const p = positions[device.id];
      expect(p.x >= box.x && p.x + NODE_W <= box.x + box.w && p.y >= box.y && p.y + NODE_H <= box.y + box.h).toBe(true);
    }
    for (let i = 0; i < boxes.length; i += 1) {
      for (let j = i + 1; j < boxes.length; j += 1) {
        const a = boxes[i];
        const b = boxes[j];
        expect(a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h).toBe(false);
      }
    }
  });
});
