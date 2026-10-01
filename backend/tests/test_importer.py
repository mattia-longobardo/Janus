from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.config import Settings
from app.importer import import_csv
from app.models import Access, Device, Event, Group
from app.net.ipplan import NetworkPlan

PLAN = NetworkPlan.from_settings(Settings())
SAMPLE = "\ufeff" + (Path(__file__).parent / "fixtures" / "sample.csv").read_text()


def test_import_sample_csv(db):
    report = import_csv(db, SAMPLE, PLAN)

    assert report.groups_created == ["Network", "People", "Smart home", "Power meters"]
    assert report.devices_created == 5
    assert report.devices_updated == 0
    assert len(report.skipped) == 2
    assert any("line 7" in s and "duplicate MAC" in s for s in report.skipped)
    assert any("line 8" in s and "quarantine pool" in s for s in report.skipped)

    people = db.scalar(select(Group).where(Group.name == "People"))
    assert (people.range_start, people.range_end) == ("192.168.1.10", "192.168.1.19")
    network = db.scalar(select(Group).where(Group.name == "Network"))
    assert (network.range_start, network.range_end) == ("192.168.1.1", "192.168.1.9")

    phone = db.scalar(select(Device).where(Device.name == "PHONE_A"))
    assert phone.mac == "02:00:5E:00:53:11" and phone.private_mac is True
    assert phone.hostname == "phone-a" and phone.access is Access.authorized
    knob = db.scalar(select(Device).where(Device.name == "KNOB"))
    assert knob.mac is None and knob.static_ip == "192.168.1.104"

    assert db.scalar(select(func.count()).select_from(Event).where(Event.type == "import.csv")) == 1


def test_import_is_idempotent(db):
    import_csv(db, SAMPLE, PLAN)
    second = import_csv(db, SAMPLE, PLAN)
    assert second.groups_created == []
    assert second.devices_created == 0
    assert second.devices_updated == 5
    assert db.scalar(select(func.count()).select_from(Device)) == 5


def test_import_updates_ip_of_known_mac(db):
    import_csv(db, SAMPLE, PLAN)
    moved = SAMPLE.replace("LAPTOP_A,00:00:5e:00:53:10,192.168.1.10", "LAPTOP_A,00:00:5e:00:53:10,192.168.1.13")
    import_csv(db, moved, PLAN)
    assert db.scalar(select(Device.static_ip).where(Device.name == "LAPTOP_A")) == "192.168.1.13"


def test_import_rejects_wrong_header(db):
    with pytest.raises(ValueError, match="missing columns"):
        import_csv(db, "Device,IP\nX,192.168.1.10\n", PLAN)


def test_import_new_device_uses_group_default_access(db):
    import_csv(db, SAMPLE, PLAN)
    meters = db.scalar(select(Group).where(Group.name == "Power meters"))
    meters.default_access = Access.lan_only
    db.flush()
    extra = SAMPLE + "PLUG_OVEN,00:00:5E:00:53:21,192.168.1.121,Power meters\n"
    import_csv(db, extra, PLAN)
    assert db.scalar(select(Device.access).where(Device.name == "PLUG_OVEN")) is Access.lan_only


def test_import_rename_regenerates_hostname(db):
    import_csv(db, SAMPLE, PLAN)
    renamed = SAMPLE.replace("LAPTOP_A,00:00:5e:00:53:10", "LAPTOP_WORK,00:00:5e:00:53:10")
    import_csv(db, renamed, PLAN)
    device = db.scalar(select(Device).where(Device.mac == "00:00:5E:00:53:10"))
    assert (device.name, device.hostname) == ("LAPTOP_WORK", "laptop-work")


def test_over_long_fields_are_skipped_not_crashing(db):
    from app.config import Settings
    from app.importer import import_csv
    from app.net.ipplan import NetworkPlan

    plan = NetworkPlan.from_settings(Settings())
    long_name = "N" * 65
    long_group = "G" * 65
    text = (
        "Name,MAC Address,LAN IP,Category\n"
        f"{long_name},00:00:5E:00:53:70,192.168.1.10,People\n"
        f"OK_PHONE,00:00:5E:00:53:71,192.168.1.11,People\n"
        f"OTHER,00:00:5E:00:53:72,192.168.1.150,{long_group}\n"
    )
    report = import_csv(db, text, plan)
    assert report.devices_created == 1
    assert any("longer than 64" in s for s in report.skipped)
    assert any(long_group[:10] in s and "longer than 64" in s for s in report.skipped)
