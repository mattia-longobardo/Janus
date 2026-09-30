from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.events import record_event
from app.maintenance import Window, muted_seconds
from app.models import Access, Device, Event, Group, Sighting

WATCHED = (Access.authorized, Access.lan_only)


def evaluate_presence(
    db: Session, *, now: datetime, timeout: timedelta, windows: list[Window], tz: ZoneInfo
) -> list[Event]:
    db.execute(
        update(Device).where(Device.online.is_(True), Device.last_seen < now - timeout).values(online=False)
    )
    alerts = []
    candidates = db.execute(
        select(Device, Group.offline_alert_hours)
        .join(Group, Device.group_id == Group.id)
        .where(
            Device.online.is_(False),
            Device.last_seen.is_not(None),
            Device.access.in_(WATCHED),
            Group.offline_alert_hours.is_not(None),
        )
    ).all()
    for device, hours in candidates:
        elapsed = (now - device.last_seen).total_seconds() - muted_seconds(windows, device.last_seen, now, tz)
        if elapsed < hours * 3600:
            continue
        already = db.scalar(
            select(Event.id).where(Event.type == "device.offline", Event.mac == device.mac, Event.ts >= device.last_seen).limit(1)
        )
        if already is None:
            alerts.append(record_event(db, "device.offline", device.mac, {
                "device_id": str(device.id), "name": device.name, "hours": hours,
                "last_seen": device.last_seen.isoformat(),
            }, ts=now))
    db.flush()
    return alerts


def purge_sightings(db: Session, before: datetime) -> int:
    result = db.execute(delete(Sighting).where(Sighting.ts < before))
    return result.rowcount or 0
