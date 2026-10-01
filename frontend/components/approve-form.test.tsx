import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApproveForm } from "@/components/approve-form";
import { makeDevice, makeGroup } from "@/lib/test-data";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

describe("ApproveForm", () => {
  const device = makeDevice({ id: "dev-1", name: "Unknown 00:53:40", dhcp_hostname: "pixel-7", access: "pending", group_id: null, static_ip: null });
  const groups = [makeGroup({ id: 1, name: "People" }), makeGroup({ id: 2, name: "Power meters", range_start: "192.168.1.120", range_end: "192.168.1.129", default_access: "lan_only" })];

  it("proposes the next free IP and posts the approval", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/groups/1/next-free-ip")) return json(200, { ip: "192.168.1.12" });
      if (url.endsWith("/devices/dev-1/approve")) return json(200, { device: { ...device, access: "authorized" }, enforcement: "dry-run" });
      throw new Error(`unexpected ${url} ${init?.method}`);
    });
    const onApproved = vi.fn();
    render(<ApproveForm device={device} groups={groups} onApproved={onApproved} />);
    const ip = screen.getByLabelText("Static IP") as HTMLInputElement;
    await waitFor(() => expect(ip.value).toBe("192.168.1.12"));
    const name = screen.getByLabelText("Name");
    await userEvent.clear(name);
    await userEvent.type(name, "PHONE_B");
    await userEvent.click(screen.getByRole("button", { name: "Approve and assign IP" }));
    await waitFor(() => expect(onApproved).toHaveBeenCalled());
    const approveCall = fetchSpy.mock.calls.find(([url]) => String(url).endsWith("/approve"))!;
    expect(JSON.parse(String(approveCall[1]?.body))).toEqual({ name: "PHONE_B", group_id: 1, static_ip: "192.168.1.12" });
  });

  it("sends an explicit access choice and shows backend errors", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("next-free-ip")) return json(200, { ip: null });
      return json(422, { detail: "no free IP left in group Power meters" });
    });
    render(<ApproveForm device={device} groups={groups} onApproved={vi.fn()} />);
    await userEvent.selectOptions(screen.getByLabelText("Group"), "2");
    await userEvent.click(screen.getByLabelText("LAN only"));
    await userEvent.click(screen.getByRole("button", { name: "Approve and assign IP" }));
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "no free IP left in group Power meters");
  });
});
