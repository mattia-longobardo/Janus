from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.intel.nmap import PortResult
from app.intel.scanning import apply_scan, pick_next
from app.models import Access, Device, Event, Group, Service

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def servers(db):
    group = Group(name="Servers", color="#F0765C", icon="server", range_start="192.168.1.220",
                  range_end="192.168.1.229", default_access=Access.authorized, scan_enabled=True, scan_interval_hours=24)
    db.add(group)
    db.flush()
    return group


def _device(db, group, mac, *, last_scan=None, online=True, access=Access.authorized, ip="192.168.1.221", requested=None):
    device = Device(mac=mac, name=f"D{mac[-2:]}", hostname=f"d{mac[-2:]}", group=group, static_ip=None, access=access,
                    online=online, last_ip=ip, last_scan_at=last_scan, scan_requested_at=requested)
    db.add(device)
    db.flush()
    return device


def _events(db, kind):
    return list(db.scalars(select(Event).where(Event.type == kind).order_by(Event.id)))


def test_due_devices_in_enabled_groups(db, servers):
    fresh = _device(db, servers, "00:00:5E:00:53:21", last_scan=NOW - timedelta(hours=1))
    due = _device(db, servers, "00:00:5E:00:53:22", last_scan=NOW - timedelta(hours=30))
    assert pick_next(db, NOW, muted=False, quiet=False) is due
    due.last_scan_at = NOW
    db.flush()
    assert pick_next(db, NOW, muted=False, quiet=False) is None
    assert fresh.last_scan_at is not None


def test_never_scanned_first_and_filters(db, servers):
    _device(db, servers, "00:00:5E:00:53:23", online=False)
    _device(db, servers, "00:00:5E:00:53:24", access=Access.pending)
    _device(db, servers, "00:00:5E:00:53:25", ip=None)
    other = Group(name="People", color="#6FB7FF", icon="device", range_start="192.168.1.10",
                  range_end="192.168.1.19", default_access=Access.authorized)
    db.add(other)
    db.flush()
    _device(db, other, "00:00:5E:00:53:26")
    assert pick_next(db, NOW, muted=False, quiet=False) is None
    never = _device(db, servers, "00:00:5E:00:53:27")
    assert pick_next(db, NOW, muted=False, quiet=False) is never


def test_schedule_skips_muted_and_quiet_but_not_requests(db, servers):
    _device(db, servers, "00:00:5E:00:53:28")
    assert pick_next(db, NOW, muted=True, quiet=False) is None
    assert pick_next(db, NOW, muted=False, quiet=True) is None
    wanted = _device(db, None, "00:00:5E:00:53:29", requested=NOW - timedelta(minutes=1))
    assert pick_next(db, NOW, muted=True, quiet=True) is wanted


def test_baseline_scan_flags_risky_but_not_new_ports(db, servers):
    device = _device(db, servers, "00:00:5E:00:53:30", requested=NOW)
    apply_scan(db, device, [PortResult(22, "tcp", "ssh", "OpenSSH 9.2p1"), PortResult(23, "tcp", "telnet", None)], NOW)
    assert _events(db, "security.new_port") == []
    [risky] = _events(db, "security.risky_service")
    assert risky.payload == {"device_id": str(device.id), "name": device.name, "risk": "high", "ports": [
        {"port": 23, "proto": "tcp", "service": "telnet", "risk": "high", "reason": "Telnet sends passwords in clear text"}]}
    assert (device.last_scan_at, device.scan_requested_at) == (NOW, None)
    assert len(_events(db, "scan.completed")) == 1


def test_second_scan_reports_new_ports_and_closes_vanished(db, servers):
    device = _device(db, servers, "00:00:5E:00:53:31")
    apply_scan(db, device, [PortResult(22, "tcp", "ssh", None), PortResult(23, "tcp", "telnet", None)], NOW)
    later = NOW + timedelta(days=1)
    apply_scan(db, device, [PortResult(22, "tcp", "ssh", None), PortResult(8080, "tcp", "http", "nginx")], later)
    [new_port] = _events(db, "security.new_port")
    assert (new_port.payload["port"], new_port.payload["service"], new_port.payload["version"]) == (8080, "http", "nginx")
    states = {s.port: s.state for s in db.scalars(select(Service).where(Service.mac == device.mac))}
    assert states == {22: "open", 23: "closed", 8080: "open"}
    apply_scan(db, device, [PortResult(22, "tcp", "ssh", None), PortResult(23, "tcp", "telnet", None),
                            PortResult(8080, "tcp", "http", "nginx")], later + timedelta(days=1))
    assert len(_events(db, "security.risky_service")) == 2
    assert len(_events(db, "security.new_port")) == 2


def test_long_banners_are_truncated(db, servers):
    device = _device(db, servers, "00:00:5E:00:53:32")
    apply_scan(db, device, [PortResult(8080, "tcp", "x" * 100, "v" * 400)], NOW)
    row = db.scalar(select(Service).where(Service.mac == device.mac))
    assert (len(row.service), len(row.version)) == (64, 255)


def test_hosts_outside_the_lan_are_never_picked(db, servers):
    _device(db, servers, "00:00:5E:00:53:33", ip="169.254.10.20")
    _device(db, None, "00:00:5E:00:53:34", ip="203.0.113.5", requested=NOW)
    assert pick_next(db, NOW, muted=False, quiet=False) is None


def test_several_risky_ports_make_one_alert(db, servers):
    device = _device(db, servers, "00:00:5E:00:53:35")
    apply_scan(db, device, [PortResult(21, "tcp", "ftp", None), PortResult(23, "tcp", "telnet", None),
                            PortResult(5900, "tcp", "vnc", None)], NOW)
    [risky] = _events(db, "security.risky_service")
    assert risky.payload["risk"] == "high"
    assert [p["port"] for p in risky.payload["ports"]] == [21, 23, 5900]


def test_muted_services_raise_no_alerts(db, servers):
    device = _device(db, servers, "00:00:5E:00:53:36")
    db.add(Service(mac=device.mac, port=23, proto="tcp", state="closed", risk="high", muted=True,
                   first_seen=NOW, last_seen=NOW))
    db.flush()
    apply_scan(db, device, [PortResult(23, "tcp", "telnet", None)], NOW)
    assert _events(db, "security.risky_service") == []
    row = db.scalar(select(Service).where(Service.mac == device.mac))
    assert (row.state, row.risk, row.muted) == ("open", "high", True)
