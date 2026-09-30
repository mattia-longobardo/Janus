from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.events import record_event
from app.maintenance import Window
from app.models import Access, Device, Event, NotificationRule, Setting
from app.notify.channels import NotifyError
from app.notify.debounce import MemoryDebouncer
from app.notify.dispatcher import dispatch_pending
from app.notify.store import NotifySettings, default_rule_rows, save_notify_settings

ROME = ZoneInfo("Europe/Rome")
NOON = datetime(2026, 10, 1, 12, 0, tzinfo=ROME)
REBOOT = [Window(time(5, 0), timedelta(minutes=15))]


def at(day, hour, minute, second=0):
    return datetime(2026, 10, day, hour, minute, second, tzinfo=ROME)


class FakeSender:
    def __init__(self, fail_times: int = 0, is_ready: bool = True, permanent: bool = False):
        self.fail_times, self.is_ready, self.permanent, self.sent = fail_times, is_ready, permanent, []

    def ready(self, ns):
        return self.is_ready

    def send(self, message, ns):
        if self.fail_times:
            self.fail_times -= 1
            raise NotifyError("boom", permanent=self.permanent)
        self.sent.append(message.title)


@pytest.fixture
def env(db):
    db.add_all([NotificationRule(**row) for row in default_rule_rows()])
    save_notify_settings(db, NotifySettings(email_recipient="owner@example.org"))
    db.flush()
    senders = {"email": FakeSender(), "gotify": FakeSender()}
    debouncer = MemoryDebouncer()

    def run(now=NOON, windows=None):
        return dispatch_pending(db, senders, debouncer, now=now, tz=ROME, windows=windows or [],
                                base_url="https://janus.example", quarantine_active=False)

    run()
    return senders, run


def emit(db, kind, mac=None, payload=None, when=NOON - timedelta(minutes=1)):
    return record_event(db, kind, mac, payload or {}, ts=when)


def _failed(db):
    return list(db.scalars(select(Event).where(Event.type == "notify.failed")))


def test_first_run_starts_after_existing_events(db):
    emit(db, "device.new", "00:00:5E:00:53:40", {"ip": "192.168.1.243"})
    senders = {"email": FakeSender(), "gotify": FakeSender()}
    assert dispatch_pending(db, senders, MemoryDebouncer(), now=NOON, tz=ROME, windows=[],
                            base_url="b", quarantine_active=False) == 0
    assert senders["gotify"].sent == []
    assert db.get(Setting, "notify.cursor").value == db.scalar(select(Event.id))


def test_new_device_goes_to_both_channels(db, env):
    senders, run = env
    emit(db, "device.new", "00:00:5E:00:53:40", {"ip": "192.168.1.243"})
    assert run() == 1
    assert senders["email"].sent == senders["gotify"].sent == ["New device: 00:00:5E:00:53:40"]


def test_recent_events_wait_until_settled(db, env):
    senders, run = env
    emit(db, "device.new", "00:00:5E:00:53:46", when=NOON - timedelta(seconds=5))
    assert run() == 0 and senders["gotify"].sent == []
    run(now=NOON + timedelta(minutes=1))
    assert senders["gotify"].sent == ["New device: 00:00:5E:00:53:46"]


def test_quiet_hours_defer_offline_until_morning(db, env):
    senders, run = env
    last_seen = at(1, 21, 0)
    db.add(Device(mac="00:00:5E:00:53:20", name="PLUG", hostname="plug", access=Access.lan_only, online=False,
                  last_seen=last_seen))
    db.flush()
    emit(db, "device.offline", "00:00:5E:00:53:20", {"name": "PLUG", "hours": 1, "last_seen": last_seen.isoformat()},
         when=at(1, 23, 30))
    emit(db, "device.new", "00:00:5E:00:53:41", when=at(1, 23, 30))
    run(now=at(1, 23, 31))
    assert senders["gotify"].sent == ["New device: 00:00:5E:00:53:41"]
    run(now=at(2, 7, 5))
    assert senders["gotify"].sent[-1] == "Offline: PLUG"


def test_deferred_offline_is_dropped_when_device_returns(db, env):
    senders, run = env
    last_seen = at(1, 21, 0)
    device = Device(mac="00:00:5E:00:53:21", name="PLUG2", hostname="plug2", access=Access.lan_only, online=False,
                    last_seen=last_seen)
    db.add(device)
    db.flush()
    emit(db, "device.offline", device.mac, {"name": "PLUG2", "hours": 1, "last_seen": last_seen.isoformat()},
         when=at(1, 23, 30))
    run(now=at(1, 23, 31))
    device.online, device.last_seen = True, at(2, 6, 0)
    db.flush()
    run(now=at(2, 7, 5))
    assert senders["gotify"].sent == []


def test_maintenance_defers_infra_down_and_sends_if_still_down(db, env):
    senders, run = env
    save_notify_settings(db, NotifySettings(quiet_start=None, quiet_end=None, email_recipient="owner@example.org"))
    db.add(Setting(key="pihole.down_since", value=at(1, 5, 5).isoformat()))
    emit(db, "infra.down", None, {"service": "pihole", "error": "x"}, when=at(1, 5, 5))
    emit(db, "device.new", "00:00:5E:00:53:42", when=at(1, 5, 5))
    run(now=at(1, 5, 6, 30), windows=REBOOT)
    assert senders["gotify"].sent == ["New device: 00:00:5E:00:53:42"]
    run(now=at(1, 5, 20), windows=REBOOT)
    assert senders["gotify"].sent[-1] == "Pi-hole unreachable"


def test_recovery_inside_window_sends_nothing(db, env):
    senders, run = env
    emit(db, "infra.down", None, {"service": "pihole", "error": "x"}, when=at(1, 5, 5))
    emit(db, "infra.up", None, {"service": "pihole", "down_since": at(1, 5, 5).isoformat()}, when=at(1, 5, 10))
    run(now=at(1, 5, 20), windows=REBOOT)
    run(now=at(1, 5, 30), windows=REBOOT)
    assert senders["gotify"].sent == [] and senders["email"].sent == []


def test_up_follows_a_delivered_down(db, env):
    senders, run = env
    db.add(Setting(key="pihole.down_since", value=at(1, 11, 0).isoformat()))
    emit(db, "infra.down", None, {"service": "pihole", "error": "x"}, when=at(1, 11, 0))
    run()
    db.get(Setting, "pihole.down_since").value = None
    emit(db, "infra.up", None, {"service": "pihole", "down_since": at(1, 11, 0).isoformat()}, when=at(1, 11, 30))
    run()
    assert senders["gotify"].sent == ["Pi-hole unreachable", "Pi-hole reachable again"]


def test_mute_is_judged_on_event_time(db, env):
    senders, run = env
    save_notify_settings(db, NotifySettings(quiet_start=None, quiet_end=None, email_recipient="owner@example.org"))
    db.add(Setting(key="pihole.down_since", value=at(1, 5, 5).isoformat()))
    emit(db, "infra.down", None, {"service": "pihole", "error": "x"}, when=at(1, 5, 5))
    run(now=at(1, 5, 30), windows=REBOOT)
    assert senders["gotify"].sent == ["Pi-hole unreachable"]


def test_duplicate_events_are_debounced(db, env):
    senders, run = env
    for _ in range(3):
        emit(db, "ip.conflict", "00:00:5E:00:53:60", {"ip": "192.168.1.10", "macs": ["A", "B"]})
    assert run() == 3
    assert senders["gotify"].sent == ["IP conflict on 192.168.1.10"]


def test_transient_failure_retries_without_blocking_or_duplicates(db, env):
    senders, run = env
    senders["gotify"].fail_times = 1
    emit(db, "device.new", "00:00:5E:00:53:43")
    emit(db, "device.new", "00:00:5E:00:53:44")
    assert run() == 2
    assert senders["email"].sent == ["New device: 00:00:5E:00:53:43", "New device: 00:00:5E:00:53:44"]
    assert senders["gotify"].sent == ["New device: 00:00:5E:00:53:44"]
    run()
    assert senders["gotify"].sent == ["New device: 00:00:5E:00:53:44", "New device: 00:00:5E:00:53:43"]
    assert len(senders["email"].sent) == 2 and _failed(db) == []


def test_permanent_failure_is_not_retried(db, env):
    senders, run = env
    senders["gotify"] = FakeSender(fail_times=99, permanent=True)
    emit(db, "device.new", "00:00:5E:00:53:47")
    run()
    run()
    assert senders["gotify"].fail_times == 98
    [failed] = _failed(db)
    assert failed.payload["errors"] == ["gotify: boom"]


def test_gives_up_after_max_attempts(db, env):
    senders, run = env
    senders["gotify"].fail_times = 99
    emit(db, "device.new", "00:00:5E:00:53:45")
    for _ in range(4):
        run()
    assert _failed(db) == []
    run()
    assert _failed(db)[0].payload["errors"] == ["gotify: boom"]


def test_channel_without_recipient_is_skipped(db, env):
    senders, run = env
    senders["email"].is_ready = False
    emit(db, "device.new", "00:00:5E:00:53:48")
    run()
    assert senders["email"].sent == [] and senders["gotify"].sent == ["New device: 00:00:5E:00:53:48"]


def test_test_event_bypasses_debounce_and_switches(db, env):
    senders, run = env
    save_notify_settings(db, NotifySettings(enabled=False, email_recipient="owner@example.org"))
    emit(db, "notify.test", None, {"channel": "email"})
    emit(db, "notify.test", None, {"channel": "email"})
    run()
    assert senders["email"].sent == ["Janus test notification", "Janus test notification"]
    assert senders["gotify"].sent == []
