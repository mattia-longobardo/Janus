import { deviceIp, ipSortKey } from "@/lib/format";
import type { Device, Group } from "@/lib/types";

export const NODE_W = 196;
export const NODE_H = 46;
const GAP_Y = 10;
const BOX_PAD = 14;
const HEADER = 30;
const COLUMN_W = NODE_W + 2 * BOX_PAD + 16;
const COLUMNS = 5;

export interface Point {
  x: number;
  y: number;
}

export interface Box extends Point {
  key: string;
  w: number;
  h: number;
}

export function groupKey(device: Device): string {
  if (device.access === "pending") return "pending";
  if (device.group_id == null) return "ungrouped";
  return `g${device.group_id}`;
}

export function autoLayout(devices: Device[], groups: Group[]): Record<string, Point> {
  const order = [
    "ungrouped",
    ...[...groups].sort((a, b) => ipSortKey(a.range_start) - ipSortKey(b.range_start)).map((g) => `g${g.id}`),
    "pending",
  ];
  const buckets = new Map<string, Device[]>(order.map((key) => [key, []]));
  for (const device of devices) buckets.get(groupKey(device))?.push(device);
  const heights = new Array<number>(COLUMNS).fill(0);
  const positions: Record<string, Point> = {};
  for (const key of order) {
    const members = (buckets.get(key) ?? []).sort((a, b) => ipSortKey(deviceIp(a)) - ipSortKey(deviceIp(b)));
    if (members.length === 0) continue;
    const column = heights.indexOf(Math.min(...heights));
    let y = heights[column] + HEADER + BOX_PAD;
    for (const device of members) {
      positions[device.id] = { x: column * COLUMN_W + BOX_PAD, y };
      y += NODE_H + GAP_Y;
    }
    heights[column] = y - GAP_Y + BOX_PAD + 28;
  }
  return positions;
}

export function groupBoxes(devices: Device[], positions: Record<string, Point>): Box[] {
  const boxes = new Map<string, Box>();
  for (const device of devices) {
    const p = positions[device.id];
    if (!p) continue;
    const key = groupKey(device);
    const left = p.x - BOX_PAD;
    const top = p.y - HEADER - BOX_PAD;
    const right = p.x + NODE_W + BOX_PAD;
    const bottom = p.y + NODE_H + BOX_PAD;
    const box = boxes.get(key);
    if (!box) {
      boxes.set(key, { key, x: left, y: top, w: right - left, h: bottom - top });
    } else {
      const x = Math.min(box.x, left);
      const y = Math.min(box.y, top);
      box.w = Math.max(box.x + box.w, right) - x;
      box.h = Math.max(box.y + box.h, bottom) - y;
      box.x = x;
      box.y = y;
    }
  }
  return [...boxes.values()];
}
