import uuid
from datetime import datetime
from ipaddress import IPv4Address

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.groups import plan
from app.db import get_db
from app.events import record_event
from app.models import Access, Device, Group
from app.net.ipplan import AssignmentError, check_assignment
from app.net.names import hostname_for

router = APIRouter(prefix="/api/devices", tags=["devices"])


class DeviceOut(BaseModel):
    id: uuid.UUID
    mac: str | None
    name: str
    hostname: str
    group_id: int
    static_ip: str | None
    access: Access
    vendor: str | None
    private_mac: bool
    online: bool
    first_seen: datetime | None
    last_seen: datetime | None

    model_config = {"from_attributes": True}


class DevicePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    group_id: int | None = None
    static_ip: str | None = None
    access: Access | None = None


def _get(db: Session, device_id: uuid.UUID) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")
    return device


@router.get("", response_model=list[DeviceOut])
def list_devices(group_id: int | None = None, access: Access | None = None,
                 db: Session = Depends(get_db)) -> list[Device]:
    query = select(Device)
    if group_id is not None:
        query = query.where(Device.group_id == group_id)
    if access is not None:
        query = query.where(Device.access == access)
    devices = list(db.scalars(query))
    return sorted(devices, key=lambda d: (d.static_ip is None, IPv4Address(d.static_ip or "0.0.0.0"), d.name))


@router.get("/{device_id}", response_model=DeviceOut)
def get_device(device_id: uuid.UUID, db: Session = Depends(get_db)) -> Device:
    return _get(db, device_id)


@router.patch("/{device_id}", response_model=DeviceOut)
def update_device(device_id: uuid.UUID, body: DevicePatch, db: Session = Depends(get_db)) -> Device:
    device = _get(db, device_id)
    fields = body.model_dump(exclude_unset=True)
    changes: dict[str, list[object]] = {}

    group = device.group
    if fields.get("group_id") is not None and fields["group_id"] != device.group_id:
        group = db.get(Group, fields["group_id"])
        if group is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown group")

    new_ip = fields.get("static_ip", device.static_ip)
    if new_ip is not None and ("static_ip" in fields or group is not device.group):
        taken = {
            IPv4Address(ip)
            for ip in db.scalars(select(Device.static_ip).where(Device.static_ip.is_not(None), Device.id != device.id))
        }
        try:
            new_ip = str(check_assignment(plan(), new_ip, group.ip_range(), taken))
        except AssignmentError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    if new_ip != device.static_ip:
        changes["static_ip"] = [device.static_ip, new_ip]
        device.static_ip = new_ip
    if group is not device.group:
        changes["group"] = [device.group.name, group.name]
        device.group = group
    if "name" in fields and fields["name"] != device.name:
        others = set(db.scalars(select(Device.hostname).where(Device.id != device.id)))
        changes["name"] = [device.name, fields["name"]]
        device.name = fields["name"]
        device.hostname = hostname_for(device.name, others)
    if fields.get("access") is not None and fields["access"] is not device.access:
        changes["access"] = [device.access.value, fields["access"].value]
        device.access = fields["access"]

    if changes:
        record_event(db, "device.updated", device.mac, {"changes": changes})
    db.commit()
    return device
