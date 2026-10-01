from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

from app.intel.identity import enrich_once, identity_once
from app.intel.oui import OuiRegistry
from app.models import Access, Device, DeviceFact, Setting, Sighting

REGISTRY = OuiRegistry.from_csv(Path(__file__).parent / "fixtures" / "oui_sample.csv")
NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
MAC = "00:00:5E:00:53:40"


def _facts(db, mac=MAC):
    return {(f.field, f.value, f.source) for f in db.scalars(select(DeviceFact).where(DeviceFact.mac == mac))}


def test_enrich_turns_sightings_into_facts_and_fills_vendor(db):
    device = Device(mac=MAC, name="TV", hostname="tv", access=Access.pending)
    db.add_all([
        device,
        Sighting(mac=MAC, ip="192.168.1.40", source="dhcp", payload={"hostname": "tv", "vendor_class": "udhcp 1.36.1"},
                 ts=NOW),
        Sighting(mac=MAC, ip="192.168.1.40", source="mdns", payload={"services": ["_googlecast._tcp"]}, ts=NOW),
    ])
    db.flush()
    assert enrich_once(db, REGISTRY) == 2
    assert _facts(db) == {
        ("hostname", "tv", "dhcp"), ("os", "Embedded Linux (BusyBox)", "dhcp"), ("type", "Embedded device", "dhcp"),
        ("services", "_googlecast._tcp", "mdns"), ("type", "Chromecast / Google TV", "mdns"),
        ("vendor", "ICANN, IANA Department", "oui"),
    }
    assert device.vendor == "ICANN, IANA Department"


def test_enrich_is_idempotent(db):
    db.add(Sighting(mac=MAC, ip="192.168.1.40", source="dhcp", payload={"hostname": "tv"}, ts=NOW))
    db.flush()
    enrich_once(db, REGISTRY)
    assert enrich_once(db, REGISTRY) == 0
    db.add(Sighting(mac=MAC, ip="192.168.1.40", source="dhcp", payload={"hostname": "tv-2"}, ts=NOW + timedelta(hours=1)))
    db.flush()
    assert enrich_once(db, REGISTRY) == 1
    assert db.scalar(select(func.count()).select_from(DeviceFact).where(DeviceFact.field == "hostname")) == 1
    assert db.scalar(select(DeviceFact.value).where(DeviceFact.field == "hostname")) == "tv-2"


def test_older_observation_does_not_overwrite_newer_fact(db):
    db.add_all([
        Sighting(mac=MAC, ip=None, source="dhcp", payload={"hostname": "new"}, ts=NOW),
        Sighting(mac=MAC, ip=None, source="dhcp", payload={"hostname": "old"}, ts=NOW - timedelta(days=1)),
    ])
    db.flush()
    enrich_once(db, REGISTRY)
    assert db.scalar(select(DeviceFact.value).where(DeviceFact.field == "hostname")) == "new"


def test_private_macs_get_no_vendor(db):
    device = Device(mac="02:00:5E:00:53:41", name="phone", hostname="phone", access=Access.pending, private_mac=True)
    db.add(device)
    db.flush()
    enrich_once(db, REGISTRY)
    assert device.vendor is None


def test_identity_once_commits_cursor(db):
    db.add(Sighting(mac=MAC, ip=None, source="netbios", payload={"hostname": "DESKTOP-A"}, ts=NOW))
    db.flush()
    assert identity_once(lambda: nullcontext(db), REGISTRY) == 1
    assert db.get(Setting, "identity.cursor").value == db.scalar(select(func.max(Sighting.id)))


def test_services_fact_accumulates(db):
    db.add_all([
        Sighting(mac=MAC, ip=None, source="mdns", payload={"services": ["_ssh._tcp"]}, ts=NOW),
        Sighting(mac=MAC, ip=None, source="mdns", payload={"services": ["_smb._tcp"]}, ts=NOW + timedelta(minutes=1)),
    ])
    db.flush()
    enrich_once(db, REGISTRY)
    assert db.scalar(select(DeviceFact.value).where(DeviceFact.field == "services")) == "_smb._tcp, _ssh._tcp"


def test_arp_sightings_are_not_walked(db):
    db.add_all([Sighting(mac=MAC, ip="192.168.1.40", source="arp", payload={}, ts=NOW) for _ in range(3)])
    db.add(Sighting(mac=MAC, ip="192.168.1.40", source="dhcp", payload={"hostname": "tv"}, ts=NOW))
    db.flush()
    assert enrich_once(db, REGISTRY) == 1
