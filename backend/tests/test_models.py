from sqlalchemy import select

from app.models import Access, Device, Event, Group


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
