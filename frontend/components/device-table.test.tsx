import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DeviceTable } from "@/components/device-table";
import { makeDevice, makeGroup } from "@/lib/test-data";

describe("DeviceTable", () => {
  it("shows name, group, IP, MAC and links to the detail page", () => {
    render(
      <DeviceTable
        devices={[makeDevice({ id: "d1", name: "TV_SALA", group_id: 1, static_ip: "192.168.1.155", private_mac: true, online: false })]}
        groups={[makeGroup({ id: 1, name: "Streaming" })]}
      />,
    );
    const row = screen.getByRole("row", { name: /TV_SALA/ });
    expect(within(row).getByRole("link", { name: "TV_SALA" }).getAttribute("href")).toBe("/devices/d1");
    expect(within(row).getByText("Streaming")).toBeTruthy();
    expect(within(row).getByText("192.168.1.155")).toBeTruthy();
    expect(within(row).getByText("private MAC")).toBeTruthy();
    expect(within(row).getByText("Offline")).toBeTruthy();
  });

  it("says when nothing matches", () => {
    render(<DeviceTable devices={[]} groups={[]} />);
    expect(screen.getByText("No devices match.")).toBeTruthy();
  });
});
