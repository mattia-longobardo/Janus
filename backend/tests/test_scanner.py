import subprocess
from contextlib import nullcontext
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.intel.scanner import NMAP_ARGS, ScanError, run_nmap, scan_once
from app.models import Access, Device, Event, Service

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
XML = """<?xml version="1.0"?><nmaprun><host><status state="up"/><ports>
<port protocol="tcp" portid="22"><state state="open"/><service name="ssh"/></port></ports></host></nmaprun>"""


class Runner:
    def __init__(self, returncode=0, stdout=XML, stderr="", raises=None):
        self.returncode, self.stdout, self.stderr, self.raises, self.calls = returncode, stdout, stderr, raises, []

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        if self.raises:
            raise self.raises
        return subprocess.CompletedProcess(cmd, self.returncode, self.stdout, self.stderr)


def test_run_nmap_builds_unprivileged_command():
    runner = Runner()
    assert run_nmap("192.168.1.40", timeout_s=180, runner=runner) == XML
    cmd, kwargs = runner.calls[0]
    assert cmd == ["nmap", *NMAP_ARGS, "--host-timeout", "180s", "-oX", "-", "192.168.1.40"]
    assert "-sT" in cmd and kwargs["timeout"] == 240


def test_run_nmap_failure():
    with pytest.raises(ScanError, match="bad target"):
        run_nmap("192.168.1.40", timeout_s=10, runner=Runner(returncode=1, stderr="bad target"))


def _requested(db):
    device = Device(mac="00:00:5E:00:53:40", name="PI", hostname="pi", access=Access.authorized, online=True,
                    last_ip="192.168.1.40", scan_requested_at=NOW)
    db.add(device)
    db.flush()
    return device


def test_scan_once_scans_requested_device(db):
    device = _requested(db)
    runner = Runner()
    assert scan_once(lambda: nullcontext(db), now=NOW, runner=runner) == device.mac
    assert db.scalar(select(Service.port).where(Service.mac == device.mac)) == 22
    assert device.last_scan_at == NOW and device.scan_requested_at is None


def test_scan_failure_is_recorded_and_not_retried_immediately(db):
    device = _requested(db)
    runner = Runner(raises=subprocess.TimeoutExpired(cmd="nmap", timeout=240))
    assert scan_once(lambda: nullcontext(db), now=NOW, runner=runner) == device.mac
    failed = db.scalar(select(Event).where(Event.type == "scan.failed"))
    assert failed.payload["ip"] == "192.168.1.40"
    assert device.scan_requested_at is None and device.last_scan_at == NOW
    assert scan_once(lambda: nullcontext(db), now=NOW, runner=runner) is None


def test_scan_once_with_nothing_to_do(db):
    assert scan_once(lambda: nullcontext(db), now=NOW, runner=Runner()) is None


DOWN = """<?xml version="1.0"?><nmaprun><host><status state="down"/><ports></ports></host></nmaprun>"""
TIMED_OUT = """<?xml version="1.0"?><nmaprun><host timedout="true"><status state="up"/><ports>
<port protocol="tcp" portid="22"><state state="open"/><service name="ssh"/></port></ports></host></nmaprun>"""


@pytest.mark.parametrize("xml", [DOWN, TIMED_OUT], ids=["host-down", "host-timeout"])
def test_incomplete_scan_is_a_failure_and_keeps_known_ports(db, xml):
    device = _requested(db)
    db.add(Service(mac=device.mac, port=445, proto="tcp", state="open", service="microsoft-ds", risk="none",
                   first_seen=NOW, last_seen=NOW))
    db.flush()
    scan_once(lambda: nullcontext(db), now=NOW, runner=Runner(stdout=xml))
    assert db.scalar(select(Event).where(Event.type == "scan.failed")) is not None
    assert db.scalar(select(Service.state).where(Service.port == 445)) == "open"
    assert device.scan_requested_at is None and device.last_scan_at == NOW


def test_error_while_saving_results_does_not_loop(db, monkeypatch):
    import app.intel.scanner as scanner_module

    device = _requested(db)

    def broken(*args, **kwargs):
        raise RuntimeError("database says no")

    monkeypatch.setattr(scanner_module, "apply_scan", broken)
    assert scan_once(lambda: nullcontext(db), now=NOW, runner=Runner()) == device.mac
    assert device.scan_requested_at is None and device.last_scan_at == NOW
    failed = db.scalar(select(Event).where(Event.type == "scan.failed"))
    assert "database says no" in failed.payload["error"]


def _scheduled(db):
    from app.models import Group

    group = Group(name="Servers", color="#F0765C", icon="server", range_start="192.168.1.220",
                  range_end="192.168.1.229", default_access=Access.authorized, scan_enabled=True)
    device = Device(mac="00:00:5E:00:53:41", name="SRV", hostname="srv", group=group, access=Access.authorized,
                    online=True, last_ip="192.168.1.221")
    db.add_all([group, device])
    db.flush()
    return device


@pytest.mark.parametrize(("hour", "minute", "scanned"), [(10, 0, True), (23, 30, False), (4, 57, False), (7, 30, False)])
def test_scheduled_scans_stay_in_the_daytime_window(db, hour, minute, scanned):
    from datetime import time as dtime
    from zoneinfo import ZoneInfo

    from app.models import MaintenanceWindow
    from app.notify.store import NotifySettings, save_notify_settings

    save_notify_settings(db, NotifySettings(quiet_start=None, quiet_end=None))
    db.add(MaintenanceWindow(name="Reboot", start_time=dtime(5, 0), duration_min=15, days=127))
    _scheduled(db)
    now = datetime(2026, 10, 1, hour, minute, tzinfo=ZoneInfo("Europe/Rome"))
    assert (scan_once(lambda: nullcontext(db), now=now, runner=Runner()) is not None) is scanned
