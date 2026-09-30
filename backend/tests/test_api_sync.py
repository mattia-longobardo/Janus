from app.api.sync import get_pihole
from app.models import Access, Device, Group
from tests.fakes import FakePihole


def _seed(db):
    g = Group(name="People", color="#6FB7FF", icon="device", range_start="192.168.1.10",
              range_end="192.168.1.19", default_access=Access.authorized)
    db.add(g)
    db.flush()
    db.add(Device(mac="00:00:5E:00:53:10", name="LAPTOP_A", hostname="laptop-a", group=g,
                  static_ip="192.168.1.10", access=Access.authorized))
    db.flush()


def test_plan_shows_diff_without_writing(client, db):
    _seed(db)
    fake = FakePihole(["garbage line"])
    client.app.dependency_overrides[get_pihole] = lambda: fake
    body = client.get("/api/sync/plan").json()
    assert body == {"to_add": ["00:00:5e:00:53:10,192.168.1.10,laptop-a,24h"], "to_remove": [],
                    "unmanaged": ["garbage line"]}
    assert fake.writes == []


def test_apply_writes(client, db):
    _seed(db)
    fake = FakePihole()
    client.app.dependency_overrides[get_pihole] = lambda: fake
    assert client.post("/api/sync/apply").status_code == 200
    assert fake.hosts == ["00:00:5e:00:53:10,192.168.1.10,laptop-a,24h"]


def test_pihole_failure_is_502(client, db):
    _seed(db)
    client.app.dependency_overrides[get_pihole] = lambda: FakePihole(fail=True)
    response = client.get("/api/sync/plan")
    assert response.status_code == 502 and "unreachable" in response.json()["detail"]
