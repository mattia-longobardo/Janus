import { deviceIp, ipSortKey } from "@/lib/format";
import type { Device, Group } from "@/lib/types";

export const TIER_W = 176;
export const TIER_H = 44;
export const NODE_W = 236;
export const NODE_H = 40;
export const BOX_W = 256;
export const BOX_HEADER = 34;
export const BOX_PAD = 10;
const NODE_STEP = 46;
const BOX_GAP = 24;
const COLUMN_STEP = 270;
const COLUMNS = 4;
const LEFT = 24;
const MODEM_Y = 20;
const GATEWAY_Y = 88;
const INFRA_Y = 168;
const INFRA_STEP = 200;
const GROUPS_Y = 264;
const INFRA_ICONS = new Set(["wifi", "router", "server"]);
const ACCESS_POINT_ICONS = new Set(["wifi", "router"]);

export type Role = "gateway" | "infra" | "member";

export interface Point {
  x: number;
  y: number;
}

export interface Box extends Point {
  key: string;
  w: number;
  h: number;
}

export type Segment = [number, number, number, number];

export interface Wires {
  modem: Point;
  solid: Segment[];
  dashed: Segment[];
  badge: Point | null;
}

function groupOf(device: Device, groups: Group[]): Group | undefined {
  return groups.find((g) => g.id === device.group_id);
}

export function roleOf(device: Device, groups: Group[], gatewayIp: string): Role {
  if (deviceIp(device) === gatewayIp) return "gateway";
  if (device.access === "pending") return "member";
  const group = groupOf(device, groups);
  return group && INFRA_ICONS.has(group.icon) ? "infra" : "member";
}

export function nodeSize(role: Role): { w: number; h: number } {
  return role === "member" ? { w: NODE_W, h: NODE_H } : { w: TIER_W, h: TIER_H };
}

export function groupKey(device: Device): string {
  if (device.access === "pending") return "pending";
  if (device.group_id == null) return "ungrouped";
  return `g${device.group_id}`;
}

const byIp = (a: Device, b: Device) => ipSortKey(deviceIp(a)) - ipSortKey(deviceIp(b)) || a.name.localeCompare(b.name);

export function autoLayout(devices: Device[], groups: Group[], gatewayIp: string): Record<string, Point> {
  const positions: Record<string, Point> = {};
  const members = devices.filter((d) => roleOf(d, groups, gatewayIp) === "member");
  const order = [
    ...[...groups].sort((a, b) => ipSortKey(a.range_start) - ipSortKey(b.range_start)).map((g) => `g${g.id}`),
    "ungrouped",
    "pending",
  ];
  const buckets = new Map<string, Device[]>(order.map((key) => [key, []]));
  for (const device of members) buckets.get(groupKey(device))?.push(device);
  const filled = order.filter((key) => (buckets.get(key) ?? []).length > 0);
  const columns = Math.max(1, Math.min(COLUMNS, filled.length));
  const heights = new Array<number>(columns).fill(GROUPS_Y);
  for (const key of filled) {
    const list = (buckets.get(key) ?? []).sort(byIp);
    const column = heights.indexOf(Math.min(...heights));
    const x = LEFT + column * COLUMN_STEP + BOX_PAD;
    let y = heights[column] + BOX_HEADER;
    for (const device of list) {
      positions[device.id] = { x, y };
      y += NODE_STEP;
    }
    heights[column] = y - NODE_STEP + NODE_H + BOX_PAD + BOX_GAP;
  }

  const width = LEFT + columns * COLUMN_STEP - (COLUMN_STEP - BOX_W);
  const center = Math.max(width / 2, TIER_W);
  for (const device of devices.filter((d) => roleOf(d, groups, gatewayIp) === "gateway")) {
    positions[device.id] = { x: center - TIER_W / 2, y: GATEWAY_Y };
  }
  const infra = devices.filter((d) => roleOf(d, groups, gatewayIp) === "infra").sort(byIp);
  const start = center - ((infra.length - 1) * INFRA_STEP) / 2 - TIER_W / 2;
  infra.forEach((device, i) => {
    positions[device.id] = { x: start + i * INFRA_STEP, y: INFRA_Y };
  });
  return positions;
}

export function groupBoxes(devices: Device[], groups: Group[], gatewayIp: string, positions: Record<string, Point>): Box[] {
  const boxes = new Map<string, Box>();
  for (const device of devices) {
    const p = positions[device.id];
    if (!p || roleOf(device, groups, gatewayIp) !== "member") continue;
    const key = groupKey(device);
    const left = p.x - BOX_PAD;
    const top = p.y - BOX_HEADER;
    const right = p.x + NODE_W + BOX_PAD;
    const bottom = p.y + NODE_H + BOX_PAD;
    const box = boxes.get(key);
    if (!box) {
      boxes.set(key, { key, x: left, y: top, w: right - left, h: bottom - top });
      continue;
    }
    const x = Math.min(box.x, left);
    const y = Math.min(box.y, top);
    box.w = Math.max(box.x + box.w, right) - x;
    box.h = Math.max(box.y + box.h, bottom) - y;
    box.x = x;
    box.y = y;
  }
  return [...boxes.values()];
}

export function wires(
  devices: Device[],
  groups: Group[],
  gatewayIp: string,
  positions: Record<string, Point>,
  boxes: Box[],
): Wires {
  const solid: Segment[] = [];
  const dashed: Segment[] = [];
  const gateway = devices.find((d) => roleOf(d, groups, gatewayIp) === "gateway" && positions[d.id]);
  const infra = devices.filter((d) => roleOf(d, groups, gatewayIp) === "infra" && positions[d.id]);
  const centerX = (p: Point) => p.x + TIER_W / 2;

  const gp = gateway ? positions[gateway.id] : null;
  const modem = gp ? { x: gp.x, y: gp.y - (GATEWAY_Y - MODEM_Y) } : { x: (boxes[0]?.x ?? LEFT) + 200, y: MODEM_Y };
  const hub = gp ?? modem;
  if (gp) solid.push([centerX(modem), modem.y + TIER_H, centerX(gp), gp.y]);

  if (infra.length > 0) {
    const tops = infra.map((d) => positions[d.id].y);
    const railY = Math.min(...tops) - 18;
    const xs = [...infra.map((d) => centerX(positions[d.id])), centerX(hub)];
    solid.push([centerX(hub), hub.y + TIER_H, centerX(hub), railY]);
    solid.push([Math.min(...xs), railY, Math.max(...xs), railY]);
    for (const d of infra) {
      const p = positions[d.id];
      solid.push([centerX(p), railY, centerX(p), p.y]);
    }
  }

  if (boxes.length === 0) return { modem, solid, dashed, badge: null };
  const busY = Math.min(...boxes.map((b) => b.y)) - 24;
  const feeders = infra.filter((d) => ACCESS_POINT_ICONS.has(groupOf(d, groups)?.icon ?? ""));
  const sources = feeders.length > 0 ? feeders.map((d) => positions[d.id]) : [hub];
  const sourceXs: number[] = [];
  for (const p of sources) {
    const x = centerX(p);
    sourceXs.push(x);
    dashed.push([x, p.y + TIER_H, x, busY]);
  }

  const columns: { x: number; boxes: Box[] }[] = [];
  for (const box of [...boxes].sort((a, b) => a.x - b.x)) {
    const column = columns.find((c) => Math.abs(c.x - box.x) < 60);
    if (column) {
      column.boxes.push(box);
      column.x = Math.min(column.x, box.x);
    } else columns.push({ x: box.x, boxes: [box] });
  }
  const spines: number[] = [];
  for (const column of columns) {
    const spineX = column.x - 8;
    spines.push(spineX);
    const headers = column.boxes.map((b) => b.y + BOX_HEADER / 2);
    dashed.push([spineX, busY, spineX, Math.max(...headers)]);
    for (const box of column.boxes) dashed.push([spineX, box.y + BOX_HEADER / 2, box.x, box.y + BOX_HEADER / 2]);
  }
  const busLeft = Math.min(...spines, ...sourceXs);
  const busRight = Math.max(...spines, ...sourceXs);
  dashed.push([busLeft, busY, busRight, busY]);
  return { modem, solid, dashed, badge: { x: busLeft + 22, y: busY - 11 } };
}
