import pytest
from sqlalchemy import select

from app.approval import ApprovalError, approve_device, block_device
from app.config import Settings
from app.models import Access, Device, Event, Group
from app.net.ipplan import AssignmentError, NetworkPlan

PLAN = NetworkPlan.from_settings(Settings())


@pytest.fixture
def meters(db):
    group = Group(name="Power meters", color="#A6D86A", icon="device", range_start="192.168.1.120",
                  range_end="192.168.1.121", default_access=Access.lan_only)
    db.add(group)
    db.flush()
    return group


@pytest.fixture
def pending(db):
    device = Device(mac="00:00:5E:00:53:40", name="ESP_4C21A0", hostname="esp-4c21a0", access=Access.pending,
                    last_ip="192.168.1.243")
    db.add(device)
    db.flush()
    return device


def test_approve_uses_next_free_ip_and_group_default(db, meters, pending):
    approve_device(db, pending, plan=PLAN, name="PLUG_STUDY", group=meters)
    assert (pending.name, pending.hostname, pending.static_ip, pending.access, pending.group) == (
        "PLUG_STUDY", "plug-study", "192.168.1.120", Access.lan_only, meters)
    event = db.scalar(select(Event).where(Event.type == "device.approved"))
    assert event.payload == {"device_id": str(pending.id), "name": "PLUG_STUDY", "group": "Power meters",
                             "ip": "192.168.1.120", "access": "lan_only", "previous_access": "pending"}


def test_approve_with_explicit_ip_and_access(db, meters, pending):
    approve_device(db, pending, plan=PLAN, name="PLUG", group=meters, access=Access.authorized, static_ip="192.168.1.121")
    assert (pending.static_ip, pending.access) == ("192.168.1.121", Access.authorized)


def test_approve_rejects_ip_outside_group(db, meters, pending):
    with pytest.raises(AssignmentError, match="outside the group range"):
        approve_device(db, pending, plan=PLAN, name="PLUG", group=meters, static_ip="192.168.1.10")


def test_approve_rejects_blocked_access_value(db, meters, pending):
    with pytest.raises(ApprovalError, match="authorized or lan_only"):
        approve_device(db, pending, plan=PLAN, name="PLUG", group=meters, access=Access.blocked)


def test_approve_requires_a_mac(db, meters):
    knob = Device(mac=None, name="KNOB", hostname="knob", access=Access.pending)
    db.add(knob)
    db.flush()
    with pytest.raises(ApprovalError, match="MAC"):
        approve_device(db, knob, plan=PLAN, name="KNOB", group=meters)


def test_approve_full_group(db, meters, pending):
    db.add_all([Device(mac=f"00:00:5E:00:53:5{i}", name=f"P{i}", hostname=f"p{i}", group=meters,
                       static_ip=f"192.168.1.12{i}", access=Access.lan_only) for i in range(2)])
    db.flush()
    with pytest.raises(ApprovalError, match="no free IP"):
        approve_device(db, pending, plan=PLAN, name="PLUG", group=meters)


def test_block(db, pending):
    block_device(db, pending)
    assert pending.access is Access.blocked
    event = db.scalar(select(Event).where(Event.type == "device.blocked"))
    assert event.payload == {"device_id": str(pending.id), "name": "ESP_4C21A0", "previous_access": "pending"}
