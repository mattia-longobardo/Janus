import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.devices import get_device_or_404
from app.db import get_db
from app.events import record_event
from app.models import Service

router = APIRouter(prefix="/api/devices", tags=["services"])


class ServicePatch(BaseModel):
    muted: bool


@router.patch("/{device_id}/services/{port}/{proto}")
def update_service(device_id: uuid.UUID, port: int, proto: str, body: ServicePatch,
                   db: Session = Depends(get_db)) -> dict[str, Any]:
    device = get_device_or_404(db, device_id)
    row = db.scalar(select(Service).where(Service.mac == device.mac, Service.port == port, Service.proto == proto))
    if device.mac is None or row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "service not found")
    if row.muted != body.muted:
        row.muted = body.muted
        record_event(db, "security.risk_muted" if body.muted else "security.risk_unmuted", device.mac, {
            "device_id": str(device.id), "name": device.name, "port": port, "proto": proto,
            "service": row.service, "risk": row.risk,
        })
    db.commit()
    return {"port": row.port, "proto": row.proto, "muted": row.muted}
