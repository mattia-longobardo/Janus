import pytest

from app.models import Access, Device, Group

PEOPLE = {"name": "People", "color": "#6FB7FF", "icon": "device",
          "range_start": "192.168.1.10", "range_end": "192.168.1.19", "default_access": "authorized"}


def test_requires_internal_token(client):
    response = client.get("/api/groups", headers={"X-Janus-Internal-Token": "wrong"})
    assert response.status_code == 401


def test_closed_when_token_not_configured(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "internal_token", "")
    assert client.get("/api/groups").status_code == 503


def test_create_and_list_group(client):
    created = client.post("/api/groups", json=PEOPLE)
    assert created.status_code == 201
    body = client.get("/api/groups").json()
    assert body == [{**PEOPLE, "id": created.json()["id"], "offline_alert_hours": None, "device_count": 0,
                     "scan_enabled": False, "scan_interval_hours": 168}]


def test_create_rejects_overlap_quarantine_duplicate_and_bad_access(client):
    client.post("/api/groups", json=PEOPLE)
    overlap = client.post("/api/groups", json={**PEOPLE, "name": "Other",
                                               "range_start": "192.168.1.15", "range_end": "192.168.1.25"})
    assert overlap.status_code == 422 and "overlaps" in overlap.json()["detail"]
    quarantine = client.post("/api/groups", json={**PEOPLE, "name": "Q",
                                                  "range_start": "192.168.1.235", "range_end": "192.168.1.244"})
    assert quarantine.status_code == 422 and "quarantine" in quarantine.json()["detail"]
    dup = client.post("/api/groups", json={**PEOPLE, "range_start": "192.168.1.30", "range_end": "192.168.1.39"})
    assert dup.status_code == 409
    pending = client.post("/api/groups", json={**PEOPLE, "name": "P", "range_start": "192.168.1.40",
                                               "range_end": "192.168.1.49", "default_access": "pending"})
    assert pending.status_code == 422


def test_patch_range_must_keep_member_ips(client, db):
    gid = client.post("/api/groups", json=PEOPLE).json()["id"]
    db.add(Device(mac="00:00:5E:00:53:10", name="A", hostname="a", group_id=gid,
                  static_ip="192.168.1.18", access=Access.authorized))
    db.flush()
    shrink = client.patch(f"/api/groups/{gid}", json={"range_end": "192.168.1.15"})
    assert shrink.status_code == 409 and "192.168.1.18" in shrink.json()["detail"]
    ok = client.patch(f"/api/groups/{gid}", json={"range_end": "192.168.1.29", "color": "#A6D86A"})
    assert ok.status_code == 200 and ok.json()["range_end"] == "192.168.1.29"


def test_delete_refuses_groups_with_devices(client, db):
    gid = client.post("/api/groups", json=PEOPLE).json()["id"]
    db.add(Device(mac=None, name="A", hostname="a", group_id=gid, static_ip=None, access=Access.authorized))
    db.flush()
    assert client.delete(f"/api/groups/{gid}").status_code == 409
    empty = client.post("/api/groups", json={**PEOPLE, "name": "Empty", "range_start": "192.168.1.30",
                                             "range_end": "192.168.1.39"}).json()["id"]
    assert client.delete(f"/api/groups/{empty}").status_code == 204
    assert db.get(Group, empty) is None


def test_next_free_ip(client, db):
    gid = client.post("/api/groups", json=PEOPLE).json()["id"]
    db.add(Device(mac=None, name="A", hostname="a", group_id=gid, static_ip="192.168.1.10", access=Access.authorized))
    db.flush()
    assert client.get(f"/api/groups/{gid}/next-free-ip").json() == {"ip": "192.168.1.11"}
    assert client.get("/api/groups/9999/next-free-ip").status_code == 404


@pytest.mark.parametrize("field", ["name", "color", "icon", "range_start", "range_end", "default_access"])
def test_patch_group_null_required_field_is_422(client, field):
    gid = client.post("/api/groups", json=PEOPLE).json()["id"]
    response = client.patch(f"/api/groups/{gid}", json={field: None})
    assert response.status_code == 422


def test_patch_group_can_clear_offline_threshold(client):
    gid = client.post("/api/groups", json={**PEOPLE, "offline_alert_hours": 6}).json()["id"]
    response = client.patch(f"/api/groups/{gid}", json={"offline_alert_hours": None})
    assert response.status_code == 200 and response.json()["offline_alert_hours"] is None


def test_patch_scan_settings(client):
    gid = client.post("/api/groups", json=PEOPLE).json()["id"]
    body = client.patch(f"/api/groups/{gid}", json={"scan_enabled": True, "scan_interval_hours": 24}).json()
    assert (body["scan_enabled"], body["scan_interval_hours"]) == (True, 24)
    assert client.patch(f"/api/groups/{gid}", json={"scan_interval_hours": 0}).status_code == 422
    assert client.patch(f"/api/groups/{gid}", json={"scan_enabled": None}).status_code == 422


def test_unique_constraint_race_is_a_409(client, db, monkeypatch):
    import app.api.groups as groups_api

    body = {"name": "Racers", "color": "#6FB7FF", "icon": "device", "range_start": "192.168.1.30",
            "range_end": "192.168.1.39"}
    assert client.post("/api/groups", json=body).status_code == 201
    monkeypatch.setattr(groups_api, "_name_taken", lambda *args, **kwargs: False)
    response = client.post("/api/groups", json={**body, "range_start": "192.168.1.40", "range_end": "192.168.1.49"})
    assert response.status_code == 409
    assert "already" in response.json()["detail"]
