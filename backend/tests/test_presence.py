from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.maintenance import Window
from app.models import Access, Device, Event, Group, Sighting
from app.presence import evaluate_presence, purge_sightings

ROME = ZoneInfo("Europe/Rome")
REBOOT = [Window(time(5, 0), timedelta(minutes=15))]
NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
TIMEOUT = timedelta(minutes=5)


@pytest.fixture
def meters(db):
    group = Group(name="Power meters", color="#A6D86A", icon="device", range_start="192.168.1.120",
                  range_end="192.168.1.129", default_access=Access.lan_only, offline_alert_hours=1)
    db.add(group)
    db.flush()
    return group


def _device(db, group, last_seen, *, access=Access.lan_only, online=True, mac="00:00:5E:00:53:20"):
    device = Device(mac=mac, name="PLUG", hostname=f"plug-{mac[-2:]}", group=group, static_ip=None, access=access,
                    online=online, last_seen=last_seen)
    db.add(device)
    db.flush()
    return device


def _alerts(db):
    return db.scalar(select(func.count()).select_from(Event).where(Event.type == "device.offline"))


def _run(db, now):
    return evaluate_presence(db, now=now, timeout=TIMEOUT, windows=REBOOT, tz=ROME)


def test_marks_offline_after_timeout_without_alert(db, meters):
    device = _device(db, meters, NOW - timedelta(minutes=10))
    _run(db, NOW)
    assert device.online is False and _alerts(db) == 0


def test_alerts_once_after_threshold(db, meters):
    device = _device(db, meters, NOW - timedelta(hours=2))
    [event] = _run(db, NOW)
    assert event.payload == {"device_id": str(device.id), "name": "PLUG", "hours": 1,
                             "last_seen": (NOW - timedelta(hours=2)).isoformat()}
    _run(db, NOW + timedelta(minutes=5))
    assert _alerts(db) == 1


def test_maintenance_time_does_not_count(db, meters):
    last_seen = datetime(2026, 10, 1, 4, 58, tzinfo=ROME)
    _device(db, meters, last_seen)
    _run(db, datetime(2026, 10, 1, 6, 5, tzinfo=ROME))
    assert _alerts(db) == 0
    _run(db, datetime(2026, 10, 1, 6, 20, tzinfo=ROME))
    assert _alerts(db) == 1


def test_no_alert_without_threshold_or_for_pending(db, meters):
    free = Group(name="People", color="#6FB7FF", icon="device", range_start="192.168.1.10",
                 range_end="192.168.1.19", default_access=Access.authorized)
    db.add(free)
    db.flush()
    _device(db, free, NOW - timedelta(hours=5), mac="00:00:5E:00:53:21")
    _device(db, meters, NOW - timedelta(hours=5), access=Access.pending, mac="00:00:5E:00:53:22")
    _run(db, NOW)
    assert _alerts(db) == 0


def test_new_outage_after_return_alerts_again(db, meters):
    device = _device(db, meters, NOW - timedelta(hours=2))
    _run(db, NOW)
    device.last_seen, device.online = NOW + timedelta(minutes=1), True
    db.flush()
    _run(db, NOW + timedelta(hours=3))
    assert _alerts(db) == 2


def test_purge_sightings(db):
    db.add_all([Sighting(mac="00:00:5E:00:53:20", source="arp", ts=NOW - timedelta(days=40)),
                Sighting(mac="00:00:5E:00:53:20", source="arp", ts=NOW)])
    db.flush()
    assert purge_sightings(db, NOW - timedelta(days=30)) == 1
    assert db.scalar(select(func.count()).select_from(Sighting)) == 1
