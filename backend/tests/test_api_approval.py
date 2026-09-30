import uuid

import pytest

from app.api.approval import get_pihole_factory
from app.config import settings
from app.models import Access, Device, Group
from tests.fakes import FakePihole


@pytest.fixture
def people(db):
    group = Group(name="People", color="#6FB7FF", icon="device", range_start="192.168.1.10",
                  range_end="192.168.1.19", default_access=Access.authorized)
    db.add(group)
    db.flush()
    return group


@pytest.fixture
def pending(db):
    device = Device(mac="00:00:5E:00:53:40", name="pixel-7", hostname="pixel-7", access=Access.pending,
                    last_ip="192.168.1.243")
    db.add(device)
    db.flush()
    return device


def _use(client, fake):
    client.app.dependency_overrides[get_pihole_factory] = lambda: (lambda: fake)


def test_approve_endpoint_dry_run(client, people, pending):
    fake = FakePihole()
    _use(client, fake)
    response = client.post(f"/api/devices/{pending.id}/approve", json={"name": "Phone B", "group_id": people.id})
    assert response.status_code == 200
    body = response.json()
    assert (body["device"]["access"], body["device"]["static_ip"], body["enforcement"]) == (
        "authorized", "192.168.1.10", "dry-run")
    assert fake.writes == []


def test_approve_endpoint_apply_mode_syncs_and_revokes_quarantine_lease(client, people, pending, monkeypatch):
    monkeypatch.setattr(settings, "sync_mode", "apply")
    fake = FakePihole()
    _use(client, fake)
    body = client.post(f"/api/devices/{pending.id}/approve", json={"name": "Phone B", "group_id": people.id}).json()
    assert body["enforcement"] == "applied"
    assert fake.hosts == ["00:00:5e:00:53:40,192.168.1.10,phone-b,24h"]
    assert ("revoke", "192.168.1.243") in fake.writes


def test_block_endpoint_apply_revokes_current_lease(client, pending, monkeypatch):
    monkeypatch.setattr(settings, "sync_mode", "apply")
    fake = FakePihole()
    _use(client, fake)
    body = client.post(f"/api/devices/{pending.id}/block").json()
    assert body["device"]["access"] == "blocked" and body["enforcement"] == "applied"
    assert fake.writes == [("revoke", "192.168.1.243")]


def test_enforcement_failure_is_reported(client, people, pending, monkeypatch):
    monkeypatch.setattr(settings, "sync_mode", "apply")
    _use(client, FakePihole(fail=True))
    response = client.post(f"/api/devices/{pending.id}/approve", json={"name": "Phone B", "group_id": people.id})
    assert response.status_code == 200
    assert response.json()["enforcement"].startswith("failed: ")
    assert response.json()["device"]["access"] == "authorized"


def test_approve_validation_errors(client, people, pending):
    _use(client, FakePihole())
    unknown_group = client.post(f"/api/devices/{pending.id}/approve", json={"name": "X", "group_id": 9999})
    assert unknown_group.status_code == 422
    bad_ip = client.post(f"/api/devices/{pending.id}/approve",
                         json={"name": "X", "group_id": people.id, "static_ip": "192.168.1.50"})
    assert bad_ip.status_code == 422 and "outside the group range" in bad_ip.json()["detail"]
    missing = client.post(f"/api/devices/{uuid.uuid4()}/approve", json={"name": "X", "group_id": people.id})
    assert missing.status_code == 404
