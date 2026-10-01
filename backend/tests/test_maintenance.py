from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.general import current_tz
from app.maintenance import ALL_DAYS, Window, active_windows, alerts_muted, load_windows, muted_seconds
from app.models import MaintenanceWindow, Setting

ROME = ZoneInfo("Europe/Rome")
REBOOT = Window(time(5, 0), timedelta(minutes=15))


def at(day: int, hour: int, minute: int) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=ROME)


def test_muted_only_inside_the_window():
    assert alerts_muted([REBOOT], at(1, 5, 5), ROME)
    assert not alerts_muted([REBOOT], at(1, 5, 15), ROME)
    assert not alerts_muted([REBOOT], at(1, 4, 59), ROME)


def test_day_mask_monday_is_bit_zero():
    weekdays = Window(time(5, 0), timedelta(minutes=15), days=0b0011111)
    assert active_windows([weekdays], at(2, 5, 5), ROME)
    assert not active_windows([weekdays], at(3, 5, 5), ROME)


def test_window_crossing_midnight():
    assert alerts_muted([Window(time(23, 50), timedelta(minutes=20))], at(2, 0, 5), ROME)


def test_window_without_mute_does_not_mute():
    assert not alerts_muted([Window(time(5, 0), timedelta(minutes=15), mute_alerts=False)], at(1, 5, 5), ROME)


def test_muted_seconds_single_and_multi_day():
    assert muted_seconds([REBOOT], at(1, 4, 58), at(1, 6, 5), ROME) == 900
    assert muted_seconds([REBOOT], at(1, 4, 0), at(3, 4, 0), ROME) == 1800
    assert muted_seconds([REBOOT], at(1, 5, 10), at(1, 6, 0), ROME) == 300


def test_overlapping_windows_are_counted_once():
    other = Window(time(5, 10), timedelta(minutes=15))
    assert muted_seconds([REBOOT, other], at(1, 4, 0), at(1, 6, 0), ROME) == 25 * 60


def test_utc_inputs_use_local_schedule():
    assert muted_seconds([REBOOT], at(1, 4, 58).astimezone(UTC), at(1, 6, 5).astimezone(UTC), ROME) == 900


def test_load_windows_skips_disabled(db):
    db.add_all([
        MaintenanceWindow(name="On", start_time=time(5, 0), duration_min=15, days=ALL_DAYS),
        MaintenanceWindow(name="Off", start_time=time(6, 0), duration_min=15, days=ALL_DAYS, enabled=False),
    ])
    db.flush()
    assert load_windows(db) == [Window(time(5, 0), timedelta(minutes=15), ALL_DAYS, True, True)]


def test_current_tz_prefers_setting_and_falls_back_to_utc(db):
    assert current_tz(db) == ZoneInfo("Europe/Rome")
    db.add(Setting(key="general.timezone", value="Europe/London"))
    db.flush()
    assert current_tz(db) == ZoneInfo("Europe/London")
    db.get(Setting, "general.timezone").value = "Mars/Olympus"
    db.flush()
    assert current_tz(db) == ZoneInfo("UTC")


def test_daily_window_on_dst_change_days():
    for midnight in (datetime(2026, 3, 29, 0, 0, tzinfo=ROME), datetime(2026, 10, 25, 0, 0, tzinfo=ROME)):
        end = datetime.combine(midnight.date() + timedelta(days=1), time(0, 0), tzinfo=ROME)
        assert muted_seconds([REBOOT], midnight, end, ROME) == 900
        assert alerts_muted([REBOOT], midnight.replace(hour=5, minute=5), ROME)


def test_windows_spanning_a_dst_change_last_their_real_duration():
    two_hours = Window(time(1, 30), timedelta(hours=2))
    spring = datetime(2026, 3, 29, 0, 0, tzinfo=ROME)
    autumn = datetime(2026, 10, 25, 0, 0, tzinfo=ROME)
    assert muted_seconds([two_hours], spring, spring.replace(hour=8), ROME) == 7200
    assert muted_seconds([two_hours], autumn, autumn.replace(hour=8), ROME) == 7200
    assert alerts_muted([two_hours], datetime(2026, 3, 29, 4, 15, tzinfo=ROME), ROME)
    assert not alerts_muted([two_hours], datetime(2026, 10, 25, 3, 0, tzinfo=ROME).replace(fold=1), ROME)


def test_window_starting_in_the_skipped_hour_still_happens_once():
    skipped = Window(time(2, 30), timedelta(minutes=15))
    spring = datetime(2026, 3, 29, 0, 0, tzinfo=ROME)
    autumn = datetime(2026, 10, 25, 0, 0, tzinfo=ROME)
    assert muted_seconds([skipped], spring, spring.replace(hour=8), ROME) == 900
    assert muted_seconds([skipped], autumn, autumn.replace(hour=8), ROME) == 900
