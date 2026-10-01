import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CustomColor } from "@/components/custom-color";

const PALETTE = ["#6FB7FF", "#B69CF0"];

describe("CustomColor", () => {
  it("accepts a colour from the picker", () => {
    const onChange = vi.fn();
    render(<CustomColor value="#6FB7FF" palette={PALETTE} onChange={onChange} />);
    fireEvent.input(screen.getByLabelText("Custom colour", { selector: "input" }), { target: { value: "#12ab34" } });
    expect(onChange).toHaveBeenCalledWith("#12AB34");
  });

  it("applies a typed hex code only when it is complete and valid", async () => {
    const onChange = vi.fn();
    render(<CustomColor value="#6FB7FF" palette={PALETTE} onChange={onChange} />);
    const field = screen.getByLabelText("Colour hex code");
    await userEvent.clear(field);
    await userEvent.type(field, "ff00");
    expect(onChange).not.toHaveBeenCalled();
    await userEvent.type(field, "AA");
    expect(onChange).toHaveBeenLastCalledWith("#FF00AA");
  });
});
