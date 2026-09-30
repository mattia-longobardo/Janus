import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.events import record_event
from app.maintenance import Window, alerts_muted
from app.models import Device, Event, Setting
from app.notify.channels import NotifyError
from app.notify.debounce import Debouncer
from app.notify.policy import channels_for
from app.notify.render import Message, render
from app.notify.store import NotifySettings, load_notify_settings, load_rules

log = logging.getLogger("janus.notify")
CURSOR_KEY = "notify.cursor"
ATTEMPTS_KEY = "notify.attempts"
DEBOUNCE_S = 3600


class Sender(Protocol):
    def ready(self, ns: NotifySettings) -> bool: ...
    def send(self, message: Message, ns: NotifySettings) -> None: ...


def debounce_key(event: Event) -> str:
    payload = event.payload or {}
    subject = event.mac or payload.get("ip") or payload.get("service") or "-"
    return f"{event.type}:{subject}"


def _attempts(db: Session, event_id: int) -> dict[str, Any]:
    row = db.get(Setting, ATTEMPTS_KEY)
    if row is None or not isinstance(row.value, dict) or row.value.get("event_id") != event_id:
        return {"event_id": event_id, "count": 0, "sent": []}
    return {"event_id": event_id, "count": row.value["count"], "sent": list(row.value["sent"])}


def dispatch_pending(
    db: Session,
    senders: Mapping[str, Sender],
    debouncer: Debouncer,
    *,
    now: datetime,
    tz: ZoneInfo,
    windows: list[Window],
    base_url: str,
    quarantine_active: bool,
    batch: int = 100,
    max_attempts: int = 5,
) -> int:
    cursor = db.get(Setting, CURSOR_KEY)
    if cursor is None:
        db.add(Setting(key=CURSOR_KEY, value=db.scalar(select(func.max(Event.id))) or 0))
        db.flush()
        return 0

    ns = load_notify_settings(db)
    rules = load_rules(db)
    muted = alerts_muted(windows, now, tz)
    local_now = now.astimezone(tz)
    ready = {name for name, sender in senders.items() if sender.ready(ns)}
    events = db.scalars(select(Event).where(Event.id > int(cursor.value)).order_by(Event.id).limit(batch)).all()

    processed = 0
    for event in events:
        channels = channels_for(event.type, event.payload or {}, rules, ns, local_now, muted, ready)
        if channels:
            state = _attempts(db, event.id)
            retrying = state["count"] > 0
            if retrying or event.type == "notify.test" or debouncer.first(debounce_key(event), DEBOUNCE_S):
                device = db.scalar(select(Device).where(Device.mac == event.mac)) if event.mac else None
                message = render(event, device.name if device else None, base_url=base_url, tz=tz,
                                 quarantine_active=quarantine_active)
                errors = []
                for channel in channels:
                    if channel in state["sent"]:
                        continue
                    try:
                        senders[channel].send(message, ns)
                        state["sent"].append(channel)
                    except NotifyError as exc:
                        errors.append(f"{channel}: {exc}")
                if errors:
                    state["count"] += 1
                    if state["count"] < max_attempts:
                        db.merge(Setting(key=ATTEMPTS_KEY, value=state))
                        log.warning("notification for event %s failed (%s), will retry", event.id, "; ".join(errors))
                        break
                    record_event(db, "notify.failed", event.mac, {"event_id": event.id, "errors": errors})
        cursor.value = event.id
        processed += 1
    db.flush()
    return processed
