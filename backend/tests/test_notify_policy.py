from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.notify.policy import channels_for, in_quiet_hours, parse_hhmm
from app.notify.store import NotifySettings, default_rule_rows

ROME = ZoneInfo("Europe/Rome")
RULES = {(r["event_type"], r["channel"]): r["enabled"] for r in default_rule_rows()}
READY = {"email", "gotify"}
NOON = datetime(2026, 10, 1, 12, 0, tzinfo=ROME)
NIGHT = datetime(2026, 10, 1, 23, 30, tzinfo=ROME)


def _channels(kind, *, ns=None, now=NOON, muted=False, ready=READY, payload=None, rules=RULES):
    return channels_for(kind, payload or {}, rules, ns or NotifySettings(), now, muted, ready)


@pytest.mark.parametrize(("moment", "expected"), [(time(23, 30), True), (time(3, 0), True), (time(7, 0), False), (time(12, 0), False)])
def test_quiet_hours_across_midnight(moment, expected):
    assert in_quiet_hours(moment, time(23, 0), time(7, 0)) is expected


def test_quiet_hours_same_day_and_disabled():
    assert in_quiet_hours(time(13, 0), time(12, 0), time(14, 0))
    assert not in_quiet_hours(time(13, 0), None, time(14, 0))
    assert not in_quiet_hours(time(13, 0), time(12, 0), time(12, 0))
    assert parse_hhmm("05:30") == time(5, 30) and parse_hhmm(None) is None


def test_default_rules_route_events():
    assert _channels("device.new") == ["email", "gotify"]
    assert _channels("device.offline") == ["gotify"]
    assert _channels("device.ip_mismatch") == ["email"]
    assert _channels("unknown.type") == []


def test_quiet_hours_keep_only_new_devices():
    assert _channels("device.offline", now=NIGHT) == []
    assert _channels("device.new", now=NIGHT) == ["email", "gotify"]


def test_maintenance_mutes_only_muteable_events():
    assert _channels("infra.down", muted=True) == []
    assert _channels("ip.conflict", muted=True) == ["email", "gotify"]
    assert _channels("device.new", muted=True) == ["email", "gotify"]


def test_global_switch_and_channel_switches():
    assert _channels("device.new", ns=NotifySettings(enabled=False)) == []
    assert _channels("device.new", ns=NotifySettings(email_enabled=False)) == ["gotify"]
    assert _channels("device.new", ready={"gotify"}) == ["gotify"]


def test_test_event_targets_one_ready_channel_even_when_disabled():
    ns = NotifySettings(enabled=False)
    assert _channels("notify.test", ns=ns, payload={"channel": "email"}) == ["email"]
    assert _channels("notify.test", payload={"channel": "email"}, ready={"gotify"}) == []
