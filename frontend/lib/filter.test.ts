import { describe, expect, it } from "vitest";

import { filterDevices } from "@/lib/filter";
import { makeDevice } from "@/lib/test-data";

const devices = [
  makeDevice({ id: "a", name: "LAPTOP_A", group_id: 1, static_ip: "192.168.1.10" }),
  makeDevice({ id: "b", name: "TV_SALA", group_id: 2, static_ip: "192.168.1.155", mac: "00:00:5E:00:53:20", vendor: "Samsung" }),
  makeDevice({ id: "c", name: "Unknown", group_id: null, static_ip: null, access: "pending", last_ip: "192.168.1.243" }),
];

describe("filterDevices", () => {
  it("searches name, IP, MAC and vendor case-insensitively", () => {
    expect(filterDevices(devices, { query: "tv_", groupId: "all", access: "all" }).map((d) => d.id)).toEqual(["b"]);
    expect(filterDevices(devices, { query: "53:20", groupId: "all", access: "all" }).map((d) => d.id)).toEqual(["b"]);
    expect(filterDevices(devices, { query: "samsung", groupId: "all", access: "all" }).map((d) => d.id)).toEqual(["b"]);
    expect(filterDevices(devices, { query: ".243", groupId: "all", access: "all" }).map((d) => d.id)).toEqual(["c"]);
  });

  it("filters by group and access and sorts by IP", () => {
    expect(filterDevices(devices, { query: "", groupId: 2, access: "all" }).map((d) => d.id)).toEqual(["b"]);
    expect(filterDevices(devices, { query: "", groupId: "all", access: "pending" }).map((d) => d.id)).toEqual(["c"]);
    expect(filterDevices(devices, { query: "", groupId: "all", access: "all" }).map((d) => d.id)).toEqual(["a", "b", "c"]);
  });
});
