from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Event
from app.net.mac import normalize_mac

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def list_events(
    type: str | None = None,
    mac: str | None = None,
    before_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = select(Event).order_by(Event.id.desc()).limit(limit)
    if type:
        query = query.where(Event.type == type)
    if mac:
        try:
            query = query.where(Event.mac == normalize_mac(mac))
        except ValueError:
            return []
    if before_id is not None:
        query = query.where(Event.id < before_id)
    return [{"id": e.id, "ts": e.ts.isoformat(), "type": e.type, "mac": e.mac, "payload": e.payload}
            for e in db.scalars(query)]
