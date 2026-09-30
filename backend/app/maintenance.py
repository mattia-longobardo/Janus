from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MaintenanceWindow

ALL_DAYS = 0b1111111


@dataclass(frozen=True)
class Window:
    start: time
    duration: timedelta
    days: int = ALL_DAYS
    mute_alerts: bool = True
    pause_isolation: bool = True

    def occurrences(self, start: datetime, end: datetime, tz: ZoneInfo) -> list[tuple[datetime, datetime]]:
        found = []
        day = (start.astimezone(tz) - self.duration).date()
        last = end.astimezone(tz).date()
        while day <= last:
            if self.days & (1 << day.weekday()):
                opens = datetime.combine(day, self.start, tzinfo=tz)
                closes = opens + self.duration
                if opens < end and closes > start:
                    found.append((opens, closes))
            day += timedelta(days=1)
        return found


def active_windows(windows: list[Window], at: datetime, tz: ZoneInfo) -> list[Window]:
    return [w for w in windows if w.occurrences(at, at + timedelta(microseconds=1), tz)]


def alerts_muted(windows: list[Window], at: datetime, tz: ZoneInfo) -> bool:
    return any(w.mute_alerts for w in active_windows(windows, at, tz))


def muted_seconds(windows: list[Window], start: datetime, end: datetime, tz: ZoneInfo) -> float:
    spans = sorted(
        (max(opens, start), min(closes, end))
        for w in windows
        if w.mute_alerts
        for opens, closes in w.occurrences(start, end, tz)
    )
    total = 0.0
    current: tuple[datetime, datetime] | None = None
    for opens, closes in spans:
        if current is None or opens > current[1]:
            if current is not None:
                total += (current[1] - current[0]).total_seconds()
            current = (opens, closes)
        else:
            current = (current[0], max(current[1], closes))
    if current is not None:
        total += (current[1] - current[0]).total_seconds()
    return total


def load_windows(db: Session) -> list[Window]:
    rows = db.scalars(select(MaintenanceWindow).where(MaintenanceWindow.enabled.is_(True)).order_by(MaintenanceWindow.id))
    return [
        Window(row.start_time, timedelta(minutes=row.duration_min), row.days, row.mute_alerts, row.pause_isolation)
        for row in rows
    ]
