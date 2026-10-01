import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ThemeToggle } from "@/components/theme-toggle";

describe("ThemeToggle", () => {
  it("stores and applies the chosen theme", async () => {
    render(<ThemeToggle />);
    expect(screen.getByRole("button", { name: "system" })).toHaveProperty("ariaPressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "dark" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("janus.theme")).toBe("dark");
    await userEvent.click(screen.getByRole("button", { name: "system" }));
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(localStorage.getItem("janus.theme")).toBeNull();
  });

  it("starts from the stored choice", () => {
    localStorage.setItem("janus.theme", "light");
    render(<ThemeToggle />);
    expect(screen.getByRole("button", { name: "light" }).getAttribute("aria-pressed")).toBe("true");
  });
});
