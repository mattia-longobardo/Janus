import { describe, expect, it, vi } from "vitest";

import { ApiError, api, errorText } from "@/lib/api";

function mockFetch(status: number, body: unknown) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(body === null ? null : JSON.stringify(body), { status, headers: { "content-type": "application/json" } }),
  );
}

describe("api", () => {
  it("sends JSON and parses JSON", async () => {
    const spy = mockFetch(200, { ok: true });
    expect(await api.post("/devices/1/approve", { name: "X" })).toEqual({ ok: true });
    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/devices/1/approve");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe('{"name":"X"}');
  });

  it("returns undefined on 204", async () => {
    mockFetch(204, null);
    expect(await api.del("/map/links/3")).toBeUndefined();
  });

  it("turns a string detail into the error message", async () => {
    mockFetch(409, { detail: "these devices are already linked" });
    await expect(api.post("/map/links", {})).rejects.toEqual(new ApiError(409, "these devices are already linked"));
  });

  it("joins pydantic validation errors", async () => {
    mockFetch(422, { detail: [{ loc: ["body", "name"], msg: "String should have at least 1 character" }, { loc: ["body", "group_id"], msg: "Field required" }] });
    await expect(api.patch("/devices/1", {})).rejects.toThrow("name: String should have at least 1 character; group_id: Field required");
  });

  it("errorText handles anything", () => {
    expect(errorText(new Error("boom"))).toBe("boom");
    expect(errorText("plain")).toBe("plain");
  });
});
