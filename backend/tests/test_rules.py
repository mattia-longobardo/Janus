from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from app.intel.rules import Fact, facts_from_sighting, facts_from_vendor, summarize


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"hostname": "pixel-7", "vendor_class": "android-dhcp-14"},
         {Fact("hostname", "pixel-7", "dhcp", 70), Fact("os", "Android 14", "dhcp", 85),
          Fact("type", "Phone or tablet", "dhcp", 70)}),
        ({"vendor_class": "MSFT 5.0"}, {Fact("os", "Windows", "dhcp", 80), Fact("type", "Computer", "dhcp", 60)}),
        ({"vendor_class": "dhcpcd-10.0.6:Linux-6.6.31+rpt-rpi-2712:aarch64:BCM2835"},
         {Fact("os", "Linux 6.6.31", "dhcp", 80)}),
        ({"vendor_class": "udhcp 1.36.1"},
         {Fact("os", "Embedded Linux (BusyBox)", "dhcp", 75), Fact("type", "Embedded device", "dhcp", 60)}),
        ({"param_list": [1, 121, 3, 6, 15, 108, 114, 119, 252, 95, 44, 46]},
         {Fact("os", "Apple iOS / macOS", "dhcp", 65), Fact("type", "Apple device", "dhcp", 60)}),
        ({"param_list": [1, 3, 28, 6]}, {Fact("os", "ESP-IDF / lwIP", "dhcp", 60), Fact("type", "IoT module", "dhcp", 60)}),
        ({"param_list": [1, 3, 6]}, set()),
    ],
)
def test_dhcp_fingerprints(payload, expected):
    assert set(facts_from_sighting("dhcp", payload)) == expected


def test_mdns_facts_pick_the_strongest_service():
    facts = set(facts_from_sighting("mdns", {"hostname": "living-tv", "model": "Chromecast",
                                             "services": ["_googlecast._tcp", "_spotify-connect._tcp"]}))
    assert facts == {
        Fact("hostname", "living-tv", "mdns", 80),
        Fact("model", "Chromecast", "mdns", 85),
        Fact("services", "_googlecast._tcp, _spotify-connect._tcp", "mdns", 90),
        Fact("type", "Chromecast / Google TV", "mdns", 80),
    }


def test_netbios_and_ssdp_facts():
    assert set(facts_from_sighting("netbios", {"hostname": "DESKTOP-A"})) == {
        Fact("hostname", "DESKTOP-A", "netbios", 60), Fact("os", "Windows or Samba host", "netbios", 35)}
    assert set(facts_from_sighting("ssdp", {"server": "Linux/4.9 UPnP/1.0 Sample-TV/1.0"})) == {
        Fact("ssdp_server", "Linux/4.9 UPnP/1.0 Sample-TV/1.0", "ssdp", 90), Fact("os", "Linux", "ssdp", 50)}
    assert facts_from_sighting("arp", {}) == []


def test_vendor_facts():
    assert set(facts_from_vendor("Espressif Inc.")) == {
        Fact("vendor", "Espressif Inc.", "oui", 90), Fact("type", "IoT module (ESP32/ESP8266)", "oui", 55)}
    assert facts_from_vendor("ICANN, IANA Department") == [Fact("vendor", "ICANN, IANA Department", "oui", 90)]


@dataclass
class Row:
    field: str
    value: str
    source: str
    confidence: int
    observed_at: datetime


def test_summary_prefers_confidence_then_recency():
    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    rows = [
        Row("type", "IoT module (ESP32/ESP8266)", "oui", 55, now),
        Row("type", "Chromecast / Google TV", "mdns", 80, now - timedelta(days=1)),
        Row("os", "Linux", "ssdp", 50, now - timedelta(hours=2)),
        Row("os", "Linux 6.6", "dhcp", 50, now),
    ]
    summary = summarize(rows)
    assert summary["type"] == {"value": "Chromecast / Google TV", "source": "mdns", "confidence": 80,
                               "observed_at": (now - timedelta(days=1)).isoformat()}
    assert summary["os"]["value"] == "Linux 6.6"
