from contextlib import nullcontext

from sqlalchemy import func, select

from app.models import Access, Device, Event, Group
from app.worker import reconcile_once
from tests.fakes import FakePihole


def _seed(db):
    g = Group(name="People", color="#6FB7FF", icon="device", range_start="192.168.1.10",
              range_end="192.168.1.19", default_access=Access.authorized)
    db.add(g)
    db.flush()
    db.add(Device(mac="00:00:5E:00:53:10", name="LAPTOP_A", hostname="laptop-a", group=g,
                  static_ip="192.168.1.10", access=Access.authorized))
    db.flush()


def _count(db, kind):
    return db.scalar(select(func.count()).select_from(Event).where(Event.type == kind))


def test_reconcile_dry_run_never_writes(db):
    _seed(db)
    fake = FakePihole()
    diff = reconcile_once(lambda: nullcontext(db), lambda: fake, lease="24h", apply=False)
    assert [h.render() for h in diff.to_add] == ["00:00:5e:00:53:10,192.168.1.10,laptop-a,24h"]
    assert fake.writes == []


def test_reconcile_apply_writes(db):
    _seed(db)
    fake = FakePihole()
    reconcile_once(lambda: nullcontext(db), lambda: fake, lease="24h", apply=True)
    assert fake.hosts == ["00:00:5e:00:53:10,192.168.1.10,laptop-a,24h"]


def test_reconcile_records_single_outage(db):
    _seed(db)
    down = FakePihole(fail=True)
    assert reconcile_once(lambda: nullcontext(db), lambda: down, lease="24h", apply=True) is None
    assert reconcile_once(lambda: nullcontext(db), lambda: down, lease="24h", apply=True) is None
    assert _count(db, "infra.down") == 1
    reconcile_once(lambda: nullcontext(db), lambda: FakePihole(), lease="24h", apply=True)
    assert _count(db, "infra.up") == 1
    reconcile_once(lambda: nullcontext(db), lambda: FakePihole(), lease="24h", apply=True)
    assert _count(db, "infra.up") == 1
