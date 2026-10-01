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
    assert client.get("/api/map").json() == {"layout_version": 1, "positions": [], "links": []}
    body = client.put("/api/map/positions", json=[{"device_id": str(a.id), "x": 10.5, "y": -4},
                                                  {"device_id": str(uuid.uuid4()), "x": 1, "y": 1}]).json()
    assert body == {"updated": 1}
    body = client.get("/api/map").json()
    assert body["positions"] == [{"device_id": str(a.id), "x": 10.5, "y": -4.0}]
    assert body["layout_version"] == 3


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


def test_positions_reject_non_finite_and_huge_values(client, pair):
    a, _ = pair
    for bad in ('NaN', 'Infinity', '1e9'):
        body = f'[{{"device_id": "{a.id}", "x": {bad}, "y": 0}}]'
        response = client.put("/api/map/positions", content=body, headers={"content-type": "application/json"})
        assert response.status_code == 422
    assert client.get("/api/map").status_code == 200


def test_reverse_duplicate_blocked_by_database(db, pair):
    from sqlalchemy.exc import IntegrityError

    from app.models import Link

    a, b = pair
    db.add(Link(source_id=a.id, target_id=b.id, kind="wired"))
    db.flush()
    db.add(Link(source_id=b.id, target_id=a.id, kind="wifi"))
    with pytest.raises(IntegrityError):
        db.flush()
