import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Fact:
    field: str
    value: str
    source: str
    confidence: int


VendorRule = tuple[re.Pattern[str], Callable[[re.Match[str]], list[tuple[str, str, int]]]]

VENDOR_CLASS_RULES: list[VendorRule] = [
    (re.compile(r"^android-dhcp-(\d+)"), lambda m: [("os", f"Android {m.group(1)}", 85), ("type", "Phone or tablet", 70)]),
    (re.compile(r"^MSFT 5\.0"), lambda m: [("os", "Windows", 80), ("type", "Computer", 60)]),
    (re.compile(r"^dhcpcd-[\d.]+:Linux-(\d+(?:\.\d+)*)", re.I), lambda m: [("os", f"Linux {m.group(1)}", 80)]),
    (re.compile(r"^dhcpcd", re.I), lambda m: [("os", "Linux", 70)]),
    (re.compile(r"^udhcp", re.I), lambda m: [("os", "Embedded Linux (BusyBox)", 75), ("type", "Embedded device", 60)]),
]

SERVICE_TYPES: dict[str, tuple[str, int]] = {
    "_googlecast._tcp": ("Chromecast / Google TV", 80),
    "_amzn-wplay._tcp": ("Amazon Fire TV", 75),
    "_airplay._tcp": ("AirPlay receiver", 70),
    "_raop._tcp": ("AirPlay speaker", 65),
    "_companion-link._tcp": ("Apple device", 70),
    "_apple-mobdev2._tcp": ("Apple device", 70),
    "_ipp._tcp": ("Printer", 85),
    "_ipps._tcp": ("Printer", 85),
    "_printer._tcp": ("Printer", 85),
    "_pdl-datastream._tcp": ("Printer", 85),
    "_hap._tcp": ("HomeKit accessory", 75),
    "_hue._tcp": ("Philips Hue bridge", 90),
    "_spotify-connect._tcp": ("Speaker", 60),
    "_smb._tcp": ("Computer or NAS", 50),
    "_ssh._tcp": ("Computer or server", 50),
}

VENDOR_TYPES: list[tuple[str, str, int]] = [
    ("espressif", "IoT module (ESP32/ESP8266)", 55),
    ("raspberry pi", "Single-board computer", 60),
    ("signify", "Smart lighting", 60),
    ("philips lighting", "Smart lighting", 60),
    ("apple", "Apple device", 50),
]


def _dhcp(payload: dict[str, Any]) -> list[Fact]:
    facts = []
    if payload.get("hostname"):
        facts.append(Fact("hostname", payload["hostname"], "dhcp", 70))
    vendor_class = payload.get("vendor_class") or ""
    for pattern, build in VENDOR_CLASS_RULES:
        match = pattern.match(vendor_class)
        if match:
            facts += [Fact(field, value, "dhcp", conf) for field, value, conf in build(match)]
            return facts
    params = tuple(payload.get("param_list") or ())
    if params[:5] == (1, 121, 3, 6, 15) and 252 in params:
        facts += [Fact("os", "Apple iOS / macOS", "dhcp", 65), Fact("type", "Apple device", "dhcp", 60)]
    elif params == (1, 3, 28, 6):
        facts += [Fact("os", "ESP-IDF / lwIP", "dhcp", 60), Fact("type", "IoT module", "dhcp", 60)]
    return facts


def _mdns(payload: dict[str, Any]) -> list[Fact]:
    facts = []
    if payload.get("hostname"):
        facts.append(Fact("hostname", payload["hostname"], "mdns", 80))
    if payload.get("model"):
        facts.append(Fact("model", payload["model"], "mdns", 85))
    services = sorted(payload.get("services") or [])
    if services:
        facts.append(Fact("services", ", ".join(services), "mdns", 90))
        known = [SERVICE_TYPES[s] for s in services if s in SERVICE_TYPES]
        if known:
            value, conf = max(known, key=lambda item: item[1])
            facts.append(Fact("type", value, "mdns", conf))
    return facts


def _ssdp(payload: dict[str, Any]) -> list[Fact]:
    server = payload.get("server")
    if not server:
        return []
    facts = [Fact("ssdp_server", server, "ssdp", 90)]
    lowered = server.lower()
    if "windows" in lowered:
        facts.append(Fact("os", "Windows", "ssdp", 60))
    elif "android" in lowered:
        facts.append(Fact("os", "Android", "ssdp", 55))
    elif "linux" in lowered:
        facts.append(Fact("os", "Linux", "ssdp", 50))
    return facts


def facts_from_sighting(source: str, payload: dict[str, Any]) -> list[Fact]:
    if source == "dhcp":
        return _dhcp(payload)
    if source == "mdns":
        return _mdns(payload)
    if source == "netbios" and payload.get("hostname"):
        return [Fact("hostname", payload["hostname"], "netbios", 60), Fact("os", "Windows or Samba host", "netbios", 35)]
    if source == "ssdp":
        return _ssdp(payload)
    return []


def facts_from_vendor(vendor: str) -> list[Fact]:
    facts = [Fact("vendor", vendor, "oui", 90)]
    lowered = vendor.lower()
    for needle, value, conf in VENDOR_TYPES:
        if needle in lowered:
            facts.append(Fact("type", value, "oui", conf))
            break
    return facts


class FactRow(Protocol):
    field: str
    value: str
    source: str
    confidence: int
    observed_at: Any


def summarize(rows: Iterable[FactRow]) -> dict[str, dict[str, Any]]:
    best: dict[str, FactRow] = {}
    for row in rows:
        current = best.get(row.field)
        if current is None or (row.confidence, row.observed_at) > (current.confidence, current.observed_at):
            best[row.field] = row
    return {
        field: {"value": row.value, "source": row.source, "confidence": row.confidence,
                "observed_at": row.observed_at.isoformat()}
        for field, row in best.items()
    }
