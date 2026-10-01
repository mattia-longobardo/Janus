import uuid

import pytest

from app.models import Access, Device


@pytest.fixture
def pair(db):
    a = Device(mac="00:00:5E:00:53:10", name="AP", hostname="ap", access=Access.authorized)
    b = Device(mac="00:00:5E:00:53:11", name="TV", hostname="tv", access=Access.authorized)
    db.add_all([a, b])
    db.flush()
    return a, b


def test_positions_round_trip(client, pair):
    a, b = pair
    assert client.get("/api/map").json() == {"positions": [], "links": []}
    body = client.put("/api/map/positions", json=[{"device_id": str(a.id), "x": 10.5, "y": -4},
                                                  {"device_id": str(uuid.uuid4()), "x": 1, "y": 1}]).json()
    assert body == {"updated": 1}
    assert client.get("/api/map").json()["positions"] == [{"device_id": str(a.id), "x": 10.5, "y": -4.0}]


def test_links(client, pair):
    a, b = pair
    created = client.post("/api/map/links", json={"source_id": str(a.id), "target_id": str(b.id), "kind": "wifi"})
    assert created.status_code == 201
    link = created.json()
    assert (link["kind"], link["label"]) == ("wifi", None)
    assert client.post("/api/map/links", json={"source_id": str(b.id), "target_id": str(a.id),
                                               "kind": "wired"}).status_code == 409
    assert client.post("/api/map/links", json={"source_id": str(a.id), "target_id": str(a.id),
                                               "kind": "wired"}).status_code == 422
    assert client.post("/api/map/links", json={"source_id": str(a.id), "target_id": str(uuid.uuid4()),
                                               "kind": "wired"}).status_code == 404
    assert client.post("/api/map/links", json={"source_id": str(a.id), "target_id": str(b.id),
                                               "kind": "fiber"}).status_code == 422
    assert [x["id"] for x in client.get("/api/map").json()["links"]] == [link["id"]]
    assert client.delete(f"/api/map/links/{link['id']}").status_code == 204
    assert client.delete(f"/api/map/links/{link['id']}").status_code == 404


def test_links_disappear_with_their_device(client, db, pair):
    a, b = pair
    client.post("/api/map/links", json={"source_id": str(a.id), "target_id": str(b.id), "kind": "wired"})
    db.delete(b)
    db.flush()
    db.expire_all()
    assert client.get("/api/map").json()["links"] == []
