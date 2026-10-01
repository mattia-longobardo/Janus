import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DeviceTable } from "@/components/device-table";
import { HealthBanner } from "@/components/health";
import { makeDevice, makeGroup } from "@/lib/test-data";

const broken = makeDevice({
  id: "d1",
  name: "SIRIO",
  health: "critical",
  issues: [{ kind: "ip_mismatch", severity: "critical", message: "Using 192.168.1.30 instead of its reserved address 192.168.1.10" }],
});

describe("device health", () => {
  it("marks only devices with problems in the table", () => {
    render(<DeviceTable devices={[broken, makeDevice({ id: "d2", name: "FINE" })]} groups={[makeGroup()]} />);
    expect(screen.getByRole("img", { name: /SIRIO needs attention: Using 192.168.1.30/ })).toBeTruthy();
    expect(screen.queryByRole("img", { name: /FINE needs attention/ })).toBeNull();
  });

  it("shows a banner with every problem, red for critical and orange for warnings", () => {
    const { rerender } = render(<HealthBanner device={broken} />);
    expect(screen.getByRole("alert").textContent).toContain("This device has a problem");
    expect(screen.getByRole("alert").textContent).toContain("reserved address 192.168.1.10");
    rerender(<HealthBanner device={{ health: "warning", issues: [{ kind: "risk", severity: "warning", message: "Moderate risk on port 1900/tcp" }] }} />);
    expect(screen.getByRole("alert").textContent).toContain("This device needs attention");
    rerender(<HealthBanner device={{ health: "ok", issues: [] }} />);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
