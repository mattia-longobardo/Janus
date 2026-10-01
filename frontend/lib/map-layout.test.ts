import { describe, expect, it } from "vitest";

import { BOX_HEADER, NODE_H, NODE_W, TIER_H, TIER_W, autoLayout, groupBoxes, groupKey, nodeSize, roleOf, wires } from "@/lib/map-layout";
import { makeDevice, makeGroup } from "@/lib/test-data";

const GATEWAY = "192.168.1.1";
const groups = [
  makeGroup({ id: 1, name: "Network", icon: "wifi", range_start: "192.168.1.2", range_end: "192.168.1.9" }),
  makeGroup({ id: 2, name: "People", icon: "device", range_start: "192.168.1.10", range_end: "192.168.1.19" }),
  makeGroup({ id: 3, name: "Power meters", icon: "activity", range_start: "192.168.1.120", range_end: "192.168.1.129" }),
  makeGroup({ id: 4, name: "Servers", icon: "server", range_start: "192.168.1.220", range_end: "192.168.1.229" }),
];
const devices = [
  makeDevice({ id: "gw", name: "Gateway", group_id: null, static_ip: null, last_ip: GATEWAY }),
  makeDevice({ id: "ap1", group_id: 1, static_ip: "192.168.1.2" }),
  makeDevice({ id: "ap2", group_id: 1, static_ip: "192.168.1.3" }),
  makeDevice({ id: "srv", group_id: 4, static_ip: "192.168.1.220" }),
  ...Array.from({ length: 9 }, (_, i) => makeDevice({ id: `m${i}`, group_id: 3, static_ip: `192.168.1.${120 + i}` })),
  ...Array.from({ length: 6 }, (_, i) => makeDevice({ id: `p${i}`, group_id: 2, static_ip: `192.168.1.${10 + i}` })),
  makeDevice({ id: "q1", access: "pending", group_id: null, static_ip: null, last_ip: "192.168.1.243" }),
];

function rect(id: string, p: { x: number; y: number }) {
  const d = devices.find((x) => x.id === id)!;
  const { w, h } = nodeSize(roleOf(d, groups, GATEWAY));
  return { x: p.x, y: p.y, w, h };
}
const overlaps = (a: { x: number; y: number; w: number; h: number }, b: typeof a) =>
  a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

describe("roles", () => {
  it("separates gateway, infrastructure and group members", () => {
    expect(roleOf(devices[0], groups, GATEWAY)).toBe("gateway");
    expect(roleOf(devices[1], groups, GATEWAY)).toBe("infra");
    expect(roleOf(devices[3], groups, GATEWAY)).toBe("infra");
    expect(roleOf(devices[4], groups, GATEWAY)).toBe("member");
    expect(nodeSize("infra")).toEqual({ w: TIER_W, h: TIER_H });
    expect(nodeSize("member")).toEqual({ w: NODE_W, h: NODE_H });
  });
});

describe("autoLayout", () => {
  const positions = autoLayout(devices, groups, GATEWAY);

  it("places every device without overlaps", () => {
    expect(Object.keys(positions).sort()).toEqual(devices.map((d) => d.id).sort());
    const ids = Object.keys(positions);
    for (let i = 0; i < ids.length; i += 1) {
      for (let j = i + 1; j < ids.length; j += 1) expect(overlaps(rect(ids[i], positions[ids[i]]), rect(ids[j], positions[ids[j]]))).toBe(false);
    }
  });

  it("stacks gateway above one infrastructure row above the groups", () => {
    const infraY = new Set(["ap1", "ap2", "srv"].map((id) => positions[id].y));
    expect(infraY.size).toBe(1);
    expect(positions.gw.y).toBeLessThan([...infraY][0]);
    const memberTop = Math.min(...devices.filter((d) => roleOf(d, groups, GATEWAY) === "member").map((d) => positions[d.id].y));
    expect([...infraY][0] + TIER_H).toBeLessThan(memberTop - BOX_HEADER);
  });

  it("keeps a group in one column ordered by IP, each inside its box, boxes apart", () => {
    const meters = devices.filter((d) => d.group_id === 3).map((d) => positions[d.id]);
    expect(new Set(meters.map((p) => p.x)).size).toBe(1);
    expect(meters.map((p) => p.y)).toEqual([...meters.map((p) => p.y)].sort((a, b) => a - b));
    const boxes = groupBoxes(devices, groups, GATEWAY, positions);
    expect(boxes.map((b) => b.key).sort()).toEqual(["g2", "g3", "pending"]);
    for (const d of devices.filter((x) => roleOf(x, groups, GATEWAY) === "member")) {
      const box = boxes.find((b) => b.key === groupKey(d))!;
      const p = positions[d.id];
      expect(p.x >= box.x && p.x + NODE_W <= box.x + box.w && p.y >= box.y + BOX_HEADER && p.y + NODE_H <= box.y + box.h).toBe(true);
    }
    for (let i = 0; i < boxes.length; i += 1) {
      for (let j = i + 1; j < boxes.length; j += 1) expect(overlaps(boxes[i], boxes[j])).toBe(false);
    }
  });
});

describe("wires", () => {
  it("draws modem, router rail and a dashed bus that reaches every box", () => {
    const positions = autoLayout(devices, groups, GATEWAY);
    const boxes = groupBoxes(devices, groups, GATEWAY, positions);
    const w = wires(devices, groups, GATEWAY, positions, boxes);
    expect(w.modem.y).toBeLessThan(positions.gw.y);
    expect(w.solid.length).toBeGreaterThanOrEqual(5);
    for (const box of boxes) {
      const headerY = box.y + BOX_HEADER / 2;
      expect(w.dashed.some(([x1, y1, x2, y2]) => y1 === headerY && y2 === headerY && Math.max(x1, x2) === box.x)).toBe(true);
    }
    expect(w.badge).not.toBeNull();
  });
});
