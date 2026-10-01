import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CompactGroup } from "@/components/compact-group";
import { makeGroup } from "@/lib/test-data";

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });

describe("CompactGroup", () => {
  it("previews the moves, then applies them on confirmation", async () => {
    const preview = {
      moves: [{ device_id: "a", name: "LAPTOP", from: "192.168.1.14", to: "192.168.1.11" }],
      unchanged: 1,
      pinned: [{ name: "Gateway", ip: "192.168.1.1" }],
    };
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async () => json(preview));
    const onDone = vi.fn();
    render(<CompactGroup group={makeGroup({ id: 7, name: "People" })} onDone={onDone} onError={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /Close gaps/ }));
    expect(await screen.findByText("1 device will get a new address")).toBeTruthy();
    expect(screen.getByText(/Gateway \(192.168.1.1\)/)).toBeTruthy();
    expect(String(fetchSpy.mock.calls[0][0])).toBe("/api/groups/7/compact?dry_run=true");
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(String(fetchSpy.mock.calls[1][0])).toBe("/api/groups/7/compact?dry_run=false");
    expect(onDone.mock.calls[0][0]).toContain("1 address renumbered");
  });

  it("says so when there is nothing to renumber", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => json({ moves: [], unchanged: 3, pinned: [] }));
    render(<CompactGroup group={makeGroup()} onDone={vi.fn()} onError={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /Close gaps/ }));
    expect(await screen.findByText(/No gaps/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Apply" })).toBeNull();
  });
});
