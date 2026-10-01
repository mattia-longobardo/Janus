from datetime import time

from sqlalchemy import select

from app.models import Access, Device, DeviceFact, Event, Group, MaintenanceWindow, NotificationRule, Service, Sighting


def test_group_and_device_round_trip(db):
    group = Group(name="People", color="#6FB7FF", icon="device",
                  range_start="192.168.1.10", range_end="192.168.1.19", default_access=Access.authorized)
    db.add(group)
    db.flush()
    device = Device(mac="00:00:5E:00:53:10", name="LAPTOP_A", hostname="laptop-a",
                    group=group, static_ip="192.168.1.10", access=Access.authorized)
    db.add(device)
    db.flush()

    loaded = db.scalar(select(Device).where(Device.hostname == "laptop-a"))
    assert loaded.group.name == "People"
    assert loaded.access is Access.authorized
    assert loaded.private_mac is False and loaded.online is False
    assert loaded.id is not None


def test_device_without_mac_is_allowed(db):
    group = Group(name="Smart home", color="#5CC8A8", icon="device",
                  range_start="192.168.1.100", range_end="192.168.1.109", default_access=Access.authorized)
    db.add_all([group, Device(mac=None, name="KNOB", hostname="knob", group=group,
                              static_ip="192.168.1.104", access=Access.authorized)])
    db.flush()
    assert db.scalar(select(Device.mac).where(Device.hostname == "knob")) is None


def test_event_payload_defaults_to_empty_dict(db):
    event = Event(type="test")
    db.add(event)
    db.flush()
    db.refresh(event)
    assert event.payload == {} and event.ts is not None


def test_pending_device_without_group(db):
    device = Device(mac="00:00:5E:00:53:40", name="Unknown", hostname="unknown", group_id=None, static_ip=None,
                    access=Access.pending, last_ip="192.168.1.243", dhcp_hostname="android-1")
    db.add(device)
    db.flush()
    assert device.group is None and device.last_ip == "192.168.1.243"


def test_sighting_window_and_rule_defaults(db):
    db.add_all([
        Sighting(mac="00:00:5E:00:53:40", ip="192.168.1.243", source="arp"),
        MaintenanceWindow(name="Reboot", start_time=time(5, 0), duration_min=15, days=127),
        NotificationRule(event_type="device.new", channel="email"),
    ])
    db.flush()
    window = db.scalar(select(MaintenanceWindow))
    assert window.enabled and window.mute_alerts and window.pause_isolation
    sighting = db.scalar(select(Sighting))
    db.refresh(sighting)
    assert sighting.payload == {} and sighting.ts is not None
    assert db.scalar(select(NotificationRule)).enabled is True


def test_group_scan_defaults_and_fact_service_rows(db):
    from datetime import UTC, datetime

    import pytest
    from sqlalchemy.exc import IntegrityError

    group = Group(name="Servers", color="#F0765C", icon="server", range_start="192.168.1.220",
                  range_end="192.168.1.229", default_access=Access.authorized)
    db.add(group)
    db.flush()
    assert (group.scan_enabled, group.scan_interval_hours) == (False, 168)
    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    db.add_all([
        DeviceFact(mac="00:00:5E:00:53:10", field="vendor", value="ICANN", source="oui", confidence=90, observed_at=now),
        Service(mac="00:00:5E:00:53:10", port=22, proto="tcp", state="open", service="ssh", risk="none",
                first_seen=now, last_seen=now),
    ])
    db.flush()
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(DeviceFact(mac="00:00:5E:00:53:10", field="vendor", value="x", source="oui", confidence=1,
                              observed_at=now))
            db.flush()
