import logging
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.events import record_event
from app.maintenance import Window, alerts_muted
from app.models import Device, Event, Setting
from app.notify.channels import NotifyError
from app.notify.debounce import Debouncer
from app.notify.policy import channels_for, suppressed_by_schedule
from app.notify.render import Message, render
from app.notify.store import NotifySettings, effective_priority, load_notify_settings, load_priorities, load_rules

log = logging.getLogger("janus.notify")
CURSOR_KEY = "notify.cursor"
PENDING_KEY = "notify.pending"
DOWN_DELIVERED_KEY = "notify.down_delivered"
DEBOUNCE_S = 3600
SETTLE = timedelta(seconds=30)
DEFERRABLE = {"infra.down", "infra.up", "device.offline"}
MAX_PENDING = 200
DISPATCH_LOCK = 0x4A414E5553


class Sender(Protocol):
    def ready(self, ns: NotifySettings) -> bool: ...
    def send(self, message: Message, ns: NotifySettings) -> None: ...


def debounce_key(event: Event) -> str:
    payload = event.payload or {}
    subject = event.mac or payload.get("ip") or payload.get("service") or "-"
    return f"{event.type}:{subject}"


def _value(db: Session, key: str, default: Any) -> Any:
    row = db.get(Setting, key)
    return row.value if row is not None and row.value is not None else default


def _still_relevant(db: Session, event: Event) -> bool:
    payload = event.payload or {}
    if event.type in ("infra.down", "infra.up"):
        down = _value(db, f"{payload.get('service')}.down_since", None)
        return down is not None if event.type == "infra.down" else down is None
    if event.type == "device.offline":
        device = db.scalar(select(Device).where(Device.mac == event.mac)) if event.mac else None
        last_seen = payload.get("last_seen")
        return (
            device is not None
            and not device.online
            and device.last_seen is not None
            and last_seen is not None
            and device.last_seen == datetime.fromisoformat(last_seen)
        )
    return True


def _entry(event: Event, channels: list[str], *, deferred: bool = False) -> dict[str, Any]:
    return {"event_id": event.id, "deferred": deferred, "channels": channels, "sent": [], "skip": [],
            "attempts": 0, "errors": []}


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
    if not db.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": DISPATCH_LOCK}):
        log.info("another dispatcher is running; skipping this round")
        return 0
    cursor = db.get(Setting, CURSOR_KEY)
    if cursor is None:
        db.add(Setting(key=CURSOR_KEY, value=db.scalar(select(func.max(Event.id))) or 0))
        db.flush()
        return 0

    ns = load_notify_settings(db)
    rules = load_rules(db)
    priorities = load_priorities(db)
    ready = {name for name, sender in senders.items() if sender.ready(ns)}
    down_delivered: dict[str, bool] = dict(_value(db, DOWN_DELIVERED_KEY, {}))
    now_local = now.astimezone(tz)
    muted_now = alerts_muted(windows, now, tz)

    def gated(event: Event) -> bool:
        return event.type == "infra.up" and not down_delivered.get((event.payload or {}).get("service", ""))

    def attempt(event: Event, entry: dict[str, Any]) -> bool:
        device = db.scalar(select(Device).where(Device.mac == event.mac)) if event.mac else None
        message = render(event, device.name if device else None, base_url=base_url, tz=tz,
                         quarantine_active=quarantine_active)
        message = replace(message, priority=effective_priority(event.type, priorities))
        transient = []
        for channel in entry["channels"]:
            if channel in entry["sent"] or channel in entry["skip"]:
                continue
            try:
                senders[channel].send(message, ns)
                entry["sent"].append(channel)
            except NotifyError as exc:
                if exc.permanent:
                    entry["skip"].append(channel)
                    entry["errors"].append(f"{channel}: {exc}")
                else:
                    transient.append(f"{channel}: {exc}")
        service = (event.payload or {}).get("service", "")
        if entry["sent"] and event.type == "infra.down":
            down_delivered[service] = True
        if entry["sent"] and event.type == "infra.up":
            down_delivered.pop(service, None)
        if transient:
            entry["attempts"] += 1
            if entry["attempts"] < max_attempts:
                log.warning("notification for event %s failed (%s), will retry", event.id, "; ".join(transient))
                return True
            entry["errors"].extend(transient)
        if entry["errors"]:
            record_event(db, "notify.failed", event.mac, {"event_id": event.id, "errors": entry["errors"]})
        return False

    kept: list[dict[str, Any]] = []
    for entry in _value(db, PENDING_KEY, []):
        event = db.get(Event, entry["event_id"])
        if event is None:
            continue
        if entry["deferred"]:
            if not _still_relevant(db, event):
                continue
            if suppressed_by_schedule(event.type, ns, now_local, muted_now):
                kept.append(entry)
                continue
            if gated(event):
                continue
            channels = channels_for(event.type, event.payload or {}, rules, ns, now_local, muted_now, ready)
            if not channels:
                continue
            entry = {**entry, "deferred": False, "channels": channels}
        if attempt(event, entry):
            kept.append(entry)

    processed = 0
    events = db.scalars(select(Event).where(Event.id > int(cursor.value)).order_by(Event.id).limit(batch)).all()
    for event in events:
        if event.ts > now - SETTLE:
            break
        cursor.value = event.id
        processed += 1
        payload = event.payload or {}
        at_local = event.ts.astimezone(tz)
        muted_then = alerts_muted(windows, event.ts, tz)
        if event.type in DEFERRABLE and ns.enabled and suppressed_by_schedule(event.type, ns, at_local, muted_then):
            if not _still_relevant(db, event):
                continue
            if suppressed_by_schedule(event.type, ns, now_local, muted_now):
                kept.append(_entry(event, [], deferred=True))
                continue
            at_local, muted_then = now_local, muted_now
        if gated(event):
            continue
        channels = channels_for(event.type, payload, rules, ns, at_local, muted_then, ready)
        if not channels:
            continue
        if event.type != "notify.test" and not debouncer.first(debounce_key(event), DEBOUNCE_S):
            continue
        entry = _entry(event, channels)
        if attempt(event, entry):
            kept.append(entry)

    db.merge(Setting(key=PENDING_KEY, value=kept[-MAX_PENDING:]))
    db.merge(Setting(key=DOWN_DELIVERED_KEY, value=down_delivered))
    db.flush()
    return processed
