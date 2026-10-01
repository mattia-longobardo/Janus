import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RulesTable } from "@/app/(app)/notifications/rules-table";

describe("RulesTable", () => {
  it("toggles one channel of one event", async () => {
    const onChange = vi.fn();
    render(
      <RulesTable
        rules={[
          { event_type: "device.new", label: "New device waiting for approval", email: true, gotify: true },
          { event_type: "device.offline", label: "Known device offline", email: false, gotify: true },
        ]}
        onChange={onChange}
      />,
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "Known device offline by email" }));
    expect(onChange).toHaveBeenCalledWith({ event_type: "device.offline", label: "Known device offline", email: true, gotify: true });
  });
});
