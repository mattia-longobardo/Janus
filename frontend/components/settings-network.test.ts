import { describe, expect, it } from "vitest";

import { errorField, networkPatch, toDraft } from "@/components/settings-network";
import { DEFAULT_SETTINGS } from "@/lib/settings-context";

describe("network settings draft", () => {
  const settings = { ...DEFAULT_SETTINGS, network: { ...DEFAULT_SETTINGS.network, pihole_url: "http://pihole:1000", sentinel_interface: "enp5s0" } };

  it("sends only changed fields, numbers as numbers and resets as null", () => {
    const draft = { ...toDraft(settings), sweep_interval_s: "120", gateway: " 192.168.1.1 ", sentinel_interface: "eth1" };
    expect(networkPatch(draft, settings, new Set())).toEqual({ sweep_interval_s: 120, sentinel_interface: "eth1" });
    expect(networkPatch(toDraft(settings), settings, new Set(["pihole_url"]))).toEqual({ pihole_url: null });
    expect(networkPatch(toDraft(settings), settings, new Set())).toEqual({});
  });

  it("maps backend messages to the field they are about", () => {
    expect(errorField("subnet: 'x' is not an IPv4 network")).toBe("subnet");
    expect(errorField("sweep_interval_s: must be between 10 and 3600 seconds")).toBe("sweep_interval_s");
    expect(errorField("quarantine pool overlaps group People (192.168.1.10–192.168.1.19)")).toBe("quarantine_start");
    expect(errorField("unknown timezone 'Mars'")).toBeNull();
  });
});
