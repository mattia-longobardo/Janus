from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Event


def record_event(
    db: Session, type: str, mac: str | None = None, payload: dict[str, Any] | None = None, *, ts: datetime | None = None
) -> Event:
    event = Event(type=type, mac=mac, payload=payload or {})
    if ts is not None:
        event.ts = ts
    db.add(event)
    db.flush()
    return event
