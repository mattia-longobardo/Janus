from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.events import record_event
from app.maintenance import Window
from app.models import Event, NotificationRule, Setting
from app.notify.channels import NotifyError
from app.notify.debounce import MemoryDebouncer
from app.notify.dispatcher import dispatch_pending
from app.notify.store import NotifySettings, default_rule_rows, save_notify_settings

ROME = ZoneInfo("Europe/Rome")
NOON = datetime(2026, 10, 1, 12, 0, tzinfo=ROME)
REBOOT = [Window(time(5, 0), timedelta(minutes=15))]


class FakeSender:
    def __init__(self, fail_times: int = 0, is_ready: bool = True):
        self.fail_times, self.is_ready, self.sent = fail_times, is_ready, []

    def ready(self, ns):
        return self.is_ready

    def send(self, message, ns):
        if self.fail_times:
            self.fail_times -= 1
            raise NotifyError("boom")
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


def test_first_run_starts_after_existing_events(db):
    record_event(db, "device.new", "00:00:5E:00:53:40", {"ip": "192.168.1.243"})
    senders = {"email": FakeSender(), "gotify": FakeSender()}
    assert dispatch_pending(db, senders, MemoryDebouncer(), now=NOON, tz=ROME, windows=[],
                            base_url="b", quarantine_active=False) == 0
    assert senders["gotify"].sent == []
    assert db.get(Setting, "notify.cursor").value == db.scalar(select(Event.id))


def test_new_device_goes_to_both_channels(db, env):
    senders, run = env
    record_event(db, "device.new", "00:00:5E:00:53:40", {"ip": "192.168.1.243"})
    assert run() == 1
    assert senders["email"].sent == senders["gotify"].sent == ["New device: 00:00:5E:00:53:40"]


def test_quiet_hours_suppress_but_advance(db, env):
    senders, run = env
    record_event(db, "device.offline", "00:00:5E:00:53:20", {"name": "PLUG", "hours": 1})
    record_event(db, "device.new", "00:00:5E:00:53:41", {})
    assert run(now=datetime(2026, 10, 1, 23, 30, tzinfo=ROME)) == 2
    assert senders["gotify"].sent == ["New device: 00:00:5E:00:53:41"]


def test_maintenance_mutes_infra_but_not_new_devices(db, env):
    senders, run = env
    record_event(db, "infra.down", None, {"service": "pihole", "error": "x"})
    record_event(db, "device.new", "00:00:5E:00:53:42", {})
    run(now=datetime(2026, 10, 1, 5, 5, tzinfo=ROME), windows=REBOOT)
    assert senders["gotify"].sent == ["New device: 00:00:5E:00:53:42"]


def test_duplicate_events_are_debounced(db, env):
    senders, run = env
    for _ in range(3):
        record_event(db, "ip.conflict", "00:00:5E:00:53:60", {"ip": "192.168.1.10", "macs": ["A", "B"]})
    assert run() == 3
    assert senders["gotify"].sent == ["IP conflict on 192.168.1.10"]


def test_failed_channel_is_retried_without_duplicates(db, env):
    senders, run = env
    senders["gotify"].fail_times = 1
    record_event(db, "device.new", "00:00:5E:00:53:43", {})
    assert run() == 0
    assert senders["email"].sent == ["New device: 00:00:5E:00:53:43"] and senders["gotify"].sent == []
    assert run() == 1
    assert senders["email"].sent == ["New device: 00:00:5E:00:53:43"]
    assert senders["gotify"].sent == ["New device: 00:00:5E:00:53:43"]


def test_gives_up_after_max_attempts(db, env):
    senders, run = env
    senders["gotify"].fail_times = 99
    record_event(db, "device.new", "00:00:5E:00:53:44", {})
    for _ in range(4):
        assert run() == 0
    assert run() >= 1
    failed = db.scalar(select(Event).where(Event.type == "notify.failed"))
    assert failed.payload["errors"] == ["gotify: boom"]


def test_channel_without_recipient_is_skipped(db, env):
    senders, run = env
    senders["email"].is_ready = False
    record_event(db, "device.new", "00:00:5E:00:53:45", {})
    run()
    assert senders["email"].sent == [] and senders["gotify"].sent == ["New device: 00:00:5E:00:53:45"]


def test_test_event_bypasses_debounce_and_switches(db, env):
    senders, run = env
    save_notify_settings(db, NotifySettings(enabled=False, email_recipient="owner@example.org"))
    record_event(db, "notify.test", None, {"channel": "email"})
    record_event(db, "notify.test", None, {"channel": "email"})
    run()
    assert senders["email"].sent == ["Janus test notification", "Janus test notification"]
    assert senders["gotify"].sent == []
