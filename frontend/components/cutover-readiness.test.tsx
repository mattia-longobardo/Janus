import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CutoverReadiness } from "@/components/cutover-readiness";

describe("CutoverReadiness", () => {
  it("runs the checks on demand and shows each result", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          ready: false,
          plan: { to_add: 3 },
          checks: [
            { name: "pihole_reachable", ok: true, detail: "Pi-hole API answers", blocking: true },
            { name: "quarantine_rules", ok: false, detail: "Pi-hole is missing the tags", blocking: true },
            { name: "write_access", ok: null, detail: "needs the admin password", blocking: false },
          ],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    render(<CutoverReadiness />);
    expect(fetchSpy).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Run checks" }));
    expect(await screen.findByText("Not ready yet")).toBeTruthy();
    expect(screen.getByText("Pi-hole is missing the tags")).toBeTruthy();
    expect(screen.getAllByLabelText(/passed|failed|unknown/).map((el) => el.getAttribute("aria-label"))).toEqual([
      "passed",
      "failed",
      "unknown",
    ]);
    expect(screen.queryByRole("button", { name: /cutover/i })).toBeNull();
  });
});
